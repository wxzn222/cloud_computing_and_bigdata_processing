"""HTTP identity and snapshot/cache regression tests using the actual ASGI app."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coursekit import common, intelligence, service


@pytest.fixture
def ready(monkeypatch, tmp_path):
    data, outputs = tmp_path / 'data', tmp_path / 'outputs'
    monkeypatch.setattr(common, 'ROOT', tmp_path)
    monkeypatch.setattr(common, 'DATA', data)
    monkeypatch.setattr(common, 'OUT', outputs)
    monkeypatch.setattr(common, '_WRITTEN', {})
    monkeypatch.setattr(service, 'DATA', data)
    monkeypatch.setattr(service, 'OUT', outputs)
    monkeypatch.setattr(intelligence, 'DATA', data)
    monkeypatch.delenv('BDP_EXPERIMENT_ID', raising=False)
    common.register_identity('20261234', '07')
    stats = data / 'gold/realtime_service.json'
    common.write_json(stats, [{'service': 'assistant', 'requests': 5, 'input_tokens': 30, 'output_tokens': 10}])
    source, target = data / 'documents.jsonl', data / 'index.json'
    source.write_text(json.dumps({'doc_id': 'quota', 'title': '模拟服务用户配额', 'text': '模拟服务的用户每周CPU推理配额为120分钟。',
                                  'version': 1, 'visibility': 'public'}, ensure_ascii=False), encoding='utf-8')
    intelligence.build_index(source, target)
    monkeypatch.setattr(service, 'load_index', lambda: intelligence.load_index(source, target))
    monkeypatch.setattr(service, 'validate_index', lambda: intelligence.validate_index(source, target))
    service._CACHE.clear()
    with TestClient(service.app) as client:
        yield client, stats, source, target
    service._CACHE.clear()


def test_all_responses_and_pages_have_registered_identity(ready):
    client = ready[0]
    for route in ['/health', '/stats', '/metrics']:
        response = client.get(route)
        assert response.status_code == 200
        assert common.verify_evidence(response.json(), '07')['student_id'] == '20261234'
    response = client.post('/ask', json={'question': '模拟服务的用户每周CPU推理配额是多少分钟？'})
    assert response.status_code == 200
    assert response.json()['refused'] is False
    common.verify_evidence(response.json(), '07')
    saved = client.get(response.json()['evidence_json_url'])
    assert saved.status_code == 200
    assert saved.json()['kind'] == 'coursekit.run'
    assert saved.json()['result'] == response.json()
    assert saved.json()['_evidence'] == response.json()['_evidence']
    page = client.get(response.json()['evidence_html_url'])
    assert page.status_code == 200
    assert page.text == common.render_evidence(saved.json())
    assert client.get('/evidence-files/forbidden.json').status_code == 404
    for route in ['/docs', '/evidence']:
        response = client.get(route)
        assert response.status_code == 200
        assert '学号 20261234' in response.text and 'run_id:' in response.text
        assert 'position:sticky' in response.text


def test_missing_identity_blocks_all_service_paths(ready):
    client = ready[0]
    (common.ROOT / 'student.json').unlink()
    for route in ['/health', '/stats', '/metrics', '/docs', '/evidence']:
        response = client.get(route)
        assert response.status_code == 503
        assert response.json()['passed'] is False
    assert client.post('/ask', json={'question': '配额'}).status_code == 503


def test_invalid_requests_and_stale_snapshots_keep_identity(ready):
    client, stats, _, _ = ready
    for body in [{'question': ' '}, {'question': '配额', 'role': 'admin'}]:
        response = client.post('/ask', json=body)
        assert response.status_code == 422
        common.verify_evidence(response.json(), '07')
    rows = common.read_json(stats)
    rows[0]['requests'] += 999
    common.write_json(stats, rows)
    for route in ['/health', '/stats']:
        response = client.get(route)
        assert response.status_code == 409
        common.verify_evidence(response.json(), '07')
    response = client.post('/ask', json={'question': '查询实时服务统计'})
    assert response.status_code == 409
    common.verify_evidence(response.json(), '07')


def test_stats_replacement_after_read_cannot_poison_cache(ready, monkeypatch):
    _, stats, _, _ = ready
    original = stats.read_bytes()
    original_read = Path.read_bytes
    changed = [{'service': 'assistant', 'requests': 1004, 'input_tokens': 30, 'output_tokens': 10}]
    def change_after_snapshot(path):
        snapshot = original_read(path)
        if path == stats:
            common.write_json(stats, changed)
        return snapshot
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, 'read_bytes', change_after_snapshot)
        first = service.ask_payload('查询实时服务统计')
    assert first['data_version'] == hashlib.sha256(original).hexdigest()
    assert first['rows'][0]['requests'] == 5
    stats.write_bytes(original)
    second = service.ask_payload('查询实时服务统计')
    assert second['cache_hit'] is True
    assert second['rows'][0]['requests'] == 5


def test_changed_stats_between_validation_and_read_rejected(ready, monkeypatch):
    _, stats, _, _ = ready
    actual_load = service.load_index
    def change_after_index_validation():
        index = actual_load()
        rows = common.read_json(stats)
        rows[0]['requests'] += 999
        common.write_json(stats, rows)
        return index
    monkeypatch.setattr(service, 'load_index', change_after_index_validation)
    with pytest.raises(service.HTTPException) as raised:
        service.ask_payload('查询实时服务统计')
    assert raised.value.status_code == 409
    assert not service._CACHE


def test_cache_cannot_carry_another_student_or_project_identity(ready, monkeypatch):
    first = service.ask_payload('查询实时服务统计')
    assert first['cache_hit'] is False
    common._write_plain_json(common.ROOT / 'student.json', {'student_id': '20265678'})
    second = service.ask_payload('查询实时服务统计')
    assert second['cache_hit'] is False
    assert second['_evidence']['student_id'] == '20265678'
    monkeypatch.setenv('BDP_EXPERIMENT_ID', '09')
    third = service.ask_payload('查询实时服务统计')
    assert third['cache_hit'] is False
    assert third['_evidence']['experiment_id'] == '09'
