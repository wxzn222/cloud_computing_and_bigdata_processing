"""Shared UTF-8 I/O and student-bound evidence; business data keeps its schema."""
import hashlib
import html
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get('BDP_ROOT', Path(__file__).resolve().parent.parent)).resolve()
DATA = ROOT / 'data'
OUT = ROOT / 'outputs'
_RUN_ID = uuid.uuid4().hex
_STARTED_AT = datetime.now(timezone.utc).isoformat()
_WRITTEN = {}


class IdentityError(ValueError):
    """A graded run must have an explicit, consistent student identity."""


def validate_student_id(student_id):
    if (not isinstance(student_id, str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', student_id)
            or student_id.upper() in {'UNREGISTERED', 'STUDENT_ID', 'YOUR_STUDENT_ID'}):
        raise IdentityError('学号不能为空、占位符或 UNREGISTERED；请输入本人1—64位字母/数字/连字符/下划线学号。')
    return student_id


def normalize_lab(lab):
    value = str(lab).zfill(2)
    if not re.fullmatch(r'0[0-9]', value):
        raise IdentityError('实验/项目编号必须为00—09。')
    return value


def require_identity():
    path = ROOT / 'student.json'
    if not path.is_file():
        raise IdentityError('缺少学号：先运行 python -m coursekit identity --student-id 本人学号 --lab 实验号。')
    try:
        value = read_json(path)
        return validate_student_id(value.get('student_id'))
    except (json.JSONDecodeError, AttributeError, OSError) as exc:
        raise IdentityError('student.json 身份记录无效，请核对本人学号。') from exc


def register_identity(student_id, lab='01'):
    student_id = validate_student_id(student_id)
    lab = normalize_lab(lab)
    path = ROOT / 'student.json'
    if path.exists():
        previous = read_json(path).get('student_id')
        if previous != student_id:
            raise IdentityError('当前目录已登记不同学号；请使用本人新的课程副本/BDP_ROOT，不能给旧结果改署名。')
    _write_plain_json(path, {'student_id': student_id, 'experiment_id': lab})
    return student_id


def evidence_metadata(lab, stage):
    return {'schema_version': 1, 'student_id': require_identity(),
            'experiment_id': normalize_lab(lab), 'run_id': _RUN_ID,
            'captured_at': _STARTED_AT, 'stage': str(stage)}


def verify_evidence(value, lab=None, student_id=None):
    expected = validate_student_id(student_id) if student_id is not None else require_identity()
    meta = value.get('_evidence') if isinstance(value, dict) else None
    if not isinstance(meta, dict) or meta.get('schema_version') != 1:
        raise IdentityError('结果缺少有效的 _evidence 学号留痕；请用本人环境重新运行。')
    if validate_student_id(meta.get('student_id')) != expected:
        raise IdentityError('结果学号与验收学号不一致。')
    actual_lab = normalize_lab(meta.get('experiment_id', ''))
    if lab is not None and actual_lab != normalize_lab(lab):
        raise IdentityError('结果实验/项目编号不一致。')
    if not isinstance(meta.get('run_id'), str) or not re.fullmatch(r'[0-9a-f]{32}', meta['run_id']):
        raise IdentityError('结果缺少有效 run_id。')
    try:
        timestamp = datetime.fromisoformat(meta['captured_at'])
        if timestamp.tzinfo is None:
            raise ValueError('timezone missing')
    except (KeyError, TypeError, ValueError) as exc:
        raise IdentityError('结果缺少有效运行时间。') from exc
    if not isinstance(meta.get('stage'), str) or not meta['stage'].strip():
        raise IdentityError('结果缺少运行阶段。')
    return meta


def _write_plain_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            name = stream.name
            stream.write(content)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def write_json(path, value):
    """Lab report dicts carry identity; array artifacts have a hash-bound sidecar."""
    path = Path(path)
    try:
        relative = path.resolve().relative_to(OUT.resolve())
    except ValueError:
        relative = None
    match = re.fullmatch(r'lab(0[0-9])', relative.parts[0]) if relative and relative.parts else None
    if match:
        meta = evidence_metadata(match[1], path.stem)
        if isinstance(value, dict):
            value = {**value, '_evidence': meta}
        _write_plain_json(path, value)
        artifact = {'file': path.resolve().relative_to(ROOT).as_posix(), 'sha256': sha256(path),
                    '_evidence': meta}
        _WRITTEN[str(path.resolve())] = artifact
        if not isinstance(value, dict):
            _write_plain_json(path.with_name(path.name + '.identity.json'), artifact)
    else:
        _write_plain_json(path, value)
    return value


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_evidence(path, lab=None):
    value = read_json(path)
    verify_evidence(value, lab)
    return value


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def render_evidence(record):
    """A native evidence view: identity stays visible while results scroll."""
    meta = record['_evidence']
    title = f"学号 {meta['student_id']} · 实验/项目 {meta['experiment_id']}"
    heading = html.escape(title)
    label = html.escape(f"run_id: {meta['run_id']} · {meta['captured_at']} · {meta['stage']}")
    body = html.escape(json.dumps(record, ensure_ascii=False, indent=2, default=str))
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{heading}</title><style>body{{margin:0;font:16px/1.6 sans-serif;background:#f4f6f8;color:#142235}}'
            'header{position:sticky;top:0;background:#142e50;color:white;padding:18px 24px;overflow-wrap:anywhere;z-index:2}'
            'header strong{font-size:24px}header small{display:block}main{padding:20px 24px}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px;border:1px solid #cbd5e1}'
            '@media print{header{position:fixed;top:0}main{padding-top:100px}}</style>'
            f'<header><strong>{heading}</strong><small>{label}</small></header>'
            '<main><p>本页展示本次运行的原始记录。截图必须完整保留顶部学号、编号、run_id和相关结果。'
            '该标识用于证据关联；原创性还须结合代码差异和现场验收。</p>'
            f'<pre>{body}</pre></main></html>')


def save_run(lab, stage, result=None, **details):
    meta = evidence_metadata(lab, stage)
    record = {'kind': 'coursekit.run', '_evidence': meta, 'result': result,
              'artifacts': [v for v in _WRITTEN.values()
                            if v['_evidence']['experiment_id'] == meta['experiment_id']], **details}
    safe_stage = re.sub(r'[^A-Za-z0-9_-]', '_', str(stage))[:80] or 'run'
    directory = OUT / ('lab' + meta['experiment_id']) / 'evidence'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (meta['run_id'] + '-' + safe_stage)
    _write_plain_json(target.with_suffix('.json'), record)
    # Keep downloaded evidence byte-identical across Windows and POSIX.
    target.with_suffix('.html').write_bytes(render_evidence(record).encode('utf-8'))
    return record, target.with_suffix('.json'), target.with_suffix('.html')


def emit(lab, stage, payload):
    record, json_path, html_path = save_run(lab, stage, payload)
    meta = record['_evidence']
    envelope = {'STUDENT_ID': meta['student_id'], 'EXPERIMENT_ID': meta['experiment_id'],
                'IDENTITY_CODE': hashlib.sha256(f"{meta['student_id']}:{meta['experiment_id']}".encode()).hexdigest()[:12],
                'RUN_ID': meta['run_id'], 'CAPTURED_AT': meta['captured_at'],
                '_evidence': meta, 'stage': stage, 'result': payload,
                'evidence_json': str(json_path), 'evidence_html': str(html_path)}
    print(json.dumps(envelope, ensure_ascii=False, indent=2, default=str))
    return payload
