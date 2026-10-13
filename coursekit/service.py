"""Lab 07: loopback-only teaching HTTP service; role is simulated, not authentication."""
from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
import threading
import time
import uuid
from collections import deque
from typing import Literal

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .common import (DATA, OUT, IdentityError, emit, evidence_metadata, normalize_lab,
                     read_json, require_identity, save_run, verify_evidence, write_json)
from .intelligence import StaleIndexError, answer, load_index, validate_index

app = FastAPI(title='模拟服务使用分析与规则查询平台', docs_url=None, redoc_url=None)
_CACHE: dict[str, dict] = {}
_LOCK = threading.RLock()
_LATENCIES = deque(maxlen=10000)
_METRICS = {'requests': 0, 'errors': 0, 'cache_hits': 0, 'cache_misses': 0}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    role: Literal['public', 'internal'] = 'public'


def service_lab():
    lab = normalize_lab(os.environ.get('BDP_EXPERIMENT_ID', '07'))
    if lab not in {'07', '09'}:
        raise IdentityError('HTTP服务实验编号只能为07或综合项目09。')
    return lab


def response_evidence(payload, stage):
    # Keep each actual response, including failures, instead of overwriting the
    # previous request's screenshot evidence in this long-running process.
    stage = stage + '-' + uuid.uuid4().hex[:12]
    meta = evidence_metadata(service_lab(), stage)
    stem = meta['run_id'] + '-' + stage
    result = {**payload, '_evidence': meta,
              'evidence_json_url': '/evidence-files/' + stem + '.json',
              'evidence_html_url': '/evidence-files/' + stem + '.html'}
    save_run(service_lab(), stage, result)
    return result


def cache_key(question: str, role: str, data_version: str, index_version: str,
              generator: str = 'extractive', stats_version: str = '',
              student_id: str = '', experiment_id: str = '') -> str:
    identity = [' '.join(question.split()), role, data_version, index_version,
                generator, stats_version, student_id, experiment_id]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode('utf-8')).hexdigest()


def current_index():
    require_identity()
    try:
        return load_index()
    except StaleIndexError as exc:
        raise HTTPException(409, str(exc)) from exc


def stats_payload(index=None) -> dict:
    index = current_index() if index is None else index
    path = DATA / 'gold' / 'realtime_service.json'
    try:
        snapshot = path.read_bytes()
    except FileNotFoundError as exc:
        raise HTTPException(503, '缺少实验04实时汇总，请先运行 lab04') from exc
    digest = hashlib.sha256(snapshot).hexdigest()
    if not index.get('stats_sha256') or digest != index['stats_sha256']:
        raise HTTPException(409, '统计快照与当前索引不一致；请重建索引后重试。')
    try:
        rows = json.loads(snapshot.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(409, '统计快照格式无效。') from exc
    # Hash and JSON are derived from the SAME bytes, never separate file reads.
    return {'tool': 'service_stats', 'data_version': digest, 'rows': rows,
            'index_version': index['index_version'], 'knowledge_data_version': index['source_sha256']}


def ask_payload(question: str, role: str = 'public') -> dict:
    student = require_identity()
    index = current_index()  # Validate before every cache lookup.
    normalized = ' '.join(question.split())
    use_stats = normalized in {'查询实时服务统计', '各服务有多少请求'}
    stats = stats_payload(index) if use_stats else None
    key = cache_key(normalized, role, index['source_sha256'], index['index_version'],
                    stats_version=stats['data_version'] if stats else '',
                    student_id=student, experiment_id=service_lab())
    with _LOCK:
        if key in _CACHE:
            _METRICS['cache_hits'] += 1
            return response_evidence({**copy.deepcopy(_CACHE[key]), 'cache_hit': True}, 'ask')
    if stats:
        result = {**stats, 'role': role, 'question': question, 'refused': False}
    else:
        try:
            result = answer(normalized, role, index=index)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    with _LOCK:
        if len(_CACHE) >= 256:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = copy.deepcopy(result)
        _METRICS['cache_misses'] += 1
    return response_evidence({**result, 'cache_hit': False}, 'ask')


@app.middleware('http')
async def measure_request(request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        try:
            require_identity()
            service_lab()
        except IdentityError as exc:
            status = 503
            return JSONResponse({'passed': False, 'identity_required': True, 'detail': str(exc)}, status_code=status)
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        with _LOCK:
            _METRICS['requests'] += 1
            _METRICS['errors'] += int(status >= 400)
            _LATENCIES.append((time.perf_counter() - start) * 1000)


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return JSONResponse(response_evidence({'detail': exc.detail, 'passed': False}, 'http_error'), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse(response_evidence({'detail': json.loads(exc.json()) if hasattr(exc, 'json') else str(exc),
                                          'passed': False}, 'invalid_request'), status_code=422)


@app.exception_handler(Exception)
async def runtime_error(request, exc):
    return JSONResponse(response_evidence({'detail': f'{type(exc).__name__}: {exc}', 'passed': False}, 'runtime_error'), status_code=500)


@app.get('/health')
def health():
    require_identity()
    try:
        manifest = validate_index()
    except StaleIndexError as exc:
        raise HTTPException(409, str(exc)) from exc
    return response_evidence({'status': 'ready', 'index_version': manifest['index_version'],
                              'data_version': manifest['source_sha256'],
                              'authentication': 'simulated_role_loopback_only'}, 'health')


@app.post('/ask')
def ask_endpoint(request: AskRequest):
    return ask_payload(request.question, request.role)


@app.get('/stats')
def stats_endpoint():
    return response_evidence(stats_payload(), 'stats')


@app.get('/metrics')
def metrics():
    with _LOCK:
        values = list(_LATENCIES)
        return response_evidence({**_METRICS, 'latency_sample_n': len(values),
                'latency_p50_ms': float(np.percentile(values, 50)) if values else None,
                'latency_p95_ms': float(np.percentile(values, 95)) if values else None,
                'cache_entries': len(_CACHE), 'scope': '当前单进程，含健康检查；耗时窗口最多10000请求'}, 'metrics')


def identity_banner():
    meta = evidence_metadata(service_lab(), 'http_screen')
    return ('<header style="position:sticky;top:0;z-index:999;background:#142e50;color:white;'
            'padding:14px 24px;font:16px/1.6 sans-serif;overflow-wrap:anywhere">'
            f'<strong style="font-size:24px">学号 {html.escape(meta["student_id"])} · 实验/项目 {meta["experiment_id"]}</strong>'
            f'<div>run_id: {meta["run_id"]} · {meta["captured_at"]}</div></header>')


@app.get('/docs', include_in_schema=False)
def docs():
    page = get_swagger_ui_html(openapi_url=app.openapi_url, title='模拟服务使用分析与规则查询平台 · 课程接口文档')
    return HTMLResponse(page.body.decode().replace('<body>', '<body>' + identity_banner(), 1))


@app.get('/evidence', response_class=HTMLResponse, include_in_schema=False)
def evidence_view():
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>课程HTTP运行证据</title><style>body{margin:0;font:16px/1.6 sans-serif;color:#142235;'
            'background:#f4f6f8}main{max-width:1100px;margin:auto;padding:24px}button,input,select{font:inherit;'
            'padding:8px;margin:4px}input{width:min(90%,600px)}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
            'padding:20px;background:white;border:1px solid #cbd5e1}</style>' + identity_banner() +
            '<main><h1>模拟服务使用分析与规则查询平台</h1>'
            '<p>平台在本人笔记本上运行，使用合成事件与虚构服务规则；服务监听本机，role是教学模拟。</p>'
            '<p>截图必须同屏保留顶部学号、编号、run_id与下面的实际响应。</p>'
            '<p><button data-route="health">健康</button><button data-route="stats">统计</button>'
            '<button data-route="metrics">指标</button></p><form id="ask">'
            '<label>问题 <input id="question" value="模拟服务的用户每周CPU推理配额是多少分钟？" maxlength="1000" required></label>'
            '<label>角色 <select id="role"><option>public</option><option>internal</option></select></label>'
            '<button>实际提问</button></form><p><a id="raw" hidden download>下载本次原始JSON</a> '
            '<a id="page" hidden download>下载本次证据HTML</a></p>'
            '<pre id="result" aria-live="polite">尚未执行请求。</pre></main>'
            '<script>const output=document.getElementById("result");'
            'async function run(path,options){output.textContent="请求中…";try{const r=await fetch(path,options);'
            'const body=await r.json();output.textContent=JSON.stringify({http_status:r.status,response:body},null,2);'
            'for(const [id,key] of [["raw","evidence_json_url"],["page","evidence_html_url"]]){'
            'const a=document.getElementById(id);a.hidden=!body[key];if(body[key])a.href=body[key];}'
            '}catch(e){output.textContent="请求失败："+String(e);}}'
            'document.querySelectorAll("[data-route]").forEach(b=>b.onclick=()=>run("/"+b.dataset.route));'
            'document.getElementById("ask").onsubmit=e=>{e.preventDefault();run("/ask",{method:"POST",'
            'headers:{"Content-Type":"application/json"},body:JSON.stringify({question:document.getElementById("question").value,'
            'role:document.getElementById("role").value})});};</script></html>')


@app.get('/evidence-files/{filename}', include_in_schema=False)
def download_evidence(filename: str):
    if not re.fullmatch(r'[0-9a-f]{32}-[A-Za-z0-9_-]+\.(json|html)', filename):
        raise HTTPException(404, '证据文件名无效。')
    directory = OUT / ('lab' + service_lab()) / 'evidence'
    path = directory / filename
    if not path.is_file() or not path.with_suffix('.json').is_file():
        raise HTTPException(404, '证据文件不存在。')
    verify_evidence(read_json(path.with_suffix('.json')), lab=service_lab())
    return FileResponse(path, filename=filename,
                        media_type='text/html; charset=utf-8' if path.suffix == '.html' else 'application/json')


def lab07(requests: int = 20) -> dict:
    require_identity()
    if requests < 2 or requests > 10000:
        raise ValueError('requests must be between 2 and 10000')
    base = os.environ.get('BDP_SERVICE_URL', 'http://127.0.0.1:8000')
    latencies, errors, hits, details = [], 0, 0, []
    with httpx.Client(base_url=base, timeout=30) as client:
        health_response = client.get('/health')
        health_response.raise_for_status()
        verify_evidence(health_response.json())
        before = client.get('/metrics').json()
        started = time.perf_counter()
        for i in range(requests):
            question = '查询实时服务统计' if i % 5 == 0 else '模拟服务的用户每周CPU推理配额是多少分钟？'
            tick = time.perf_counter()
            response = client.post('/ask', json={'question': question, 'role': 'public'})
            elapsed = (time.perf_counter() - tick) * 1000
            latencies.append(elapsed)
            errors += int(response.status_code >= 400)
            body = response.json()
            verify_evidence(body)
            hits += int(body.get('cache_hit', False))
            details.append({'request_no': i + 1, 'question': question,
                            'status': response.status_code, 'latency_ms': elapsed, 'response': body})
        seconds = time.perf_counter() - started
        after = client.get('/metrics').json()
    report = {'requests': requests, 'concurrency': 1, 'errors': errors, 'error_rate': errors / requests,
              'wall_seconds': seconds, 'throughput_requests_per_second': requests / seconds,
              'p50_ms': float(np.percentile(latencies, 50)), 'p95_ms': float(np.percentile(latencies, 95)),
              'cache_hits': hits, 'cache_hit_rate': hits / requests,
              'server_metrics_before': before, 'server_metrics_after': after,
              'health': health_response.json(), 'details': details,
              'limitations': '串行本机HTTP测量，不是最大承载量；摘录服务耗时不是LLM推理耗时。'}
    write_json(OUT / 'lab07' / 'load_test.json', report)
    return emit('07', 'http_benchmark', {k: v for k, v in report.items() if k != 'details'})
