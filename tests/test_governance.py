import copy
import json
import sqlite3
from pathlib import Path

import pytest

from coursekit import common, governance, intelligence, pipeline


REPORTS = [('01', 'storage.json'), ('02', 'quality.json'), ('03', 'benchmark.json'),
           ('04', 'replay.json'), ('05', 'retrieval.json'),
           ('06', 'evaluation_test_extractive.json'), ('07', 'load_test.json')]


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('BDP_ROOT', str(tmp_path))
    monkeypatch.setattr(common, 'ROOT', tmp_path)
    monkeypatch.setattr(common, '_WRITTEN', {})
    for module in [common, governance, intelligence, pipeline]:
        monkeypatch.setattr(module, 'DATA', tmp_path / 'data')
        monkeypatch.setattr(module, 'OUT', tmp_path / 'outputs')
    for module in [intelligence, governance]:
        monkeypatch.setattr(module, 'SOURCE', common.DATA / 'raw/documents.jsonl')
        monkeypatch.setattr(module, 'INDEX', common.DATA / 'indexes/knowledge.json')
        monkeypatch.setattr(module, 'QUESTIONS', common.DATA / 'raw/questions.jsonl')
    monkeypatch.setattr(governance, 'emit', lambda lab, stage, value: value)
    common.write_json(tmp_path / 'student.json', {'student_id': 'TEST20260001'})
    return tmp_path


def write_raw(path, value):
    """Simulate importing an existing report, without re-signing it as this student."""
    Path(path).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


@pytest.fixture
def index(root, monkeypatch):
    common.write_json(common.DATA / 'gold/realtime_service.json', [
        {'service': 'search', 'requests': 3, 'input_tokens': 30, 'output_tokens': 9}])
    intelligence.seed_corpus()
    result = intelligence.build_index(intelligence.SOURCE, intelligence.INDEX)
    original_load = intelligence.load_index
    load_current = lambda source=intelligence.SOURCE, index_path=intelligence.INDEX: original_load(source, index_path)
    monkeypatch.setattr(intelligence, 'load_index', load_current)
    monkeypatch.setattr(governance, 'load_index', load_current)
    monkeypatch.setattr(governance, 'validate_index', lambda source=intelligence.SOURCE, index_path=intelligence.INDEX:
                        intelligence.validate_index(source, index_path))
    return result


@pytest.fixture
def replay(index):
    source = common.DATA / 'silver/events.parquet'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'input identity fixture; replay validation only reads its hash')
    database = common.DATA / 'state/runs/test-run/events.sqlite'
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as conn:
        conn.executescript('''CREATE TABLE events(event_id TEXT PRIMARY KEY,event_time TEXT NOT NULL,
            service TEXT NOT NULL,model TEXT NOT NULL,input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,latency_ms INTEGER NOT NULL,status TEXT NOT NULL);
            CREATE TABLE checkpoint(id INTEGER PRIMARY KEY CHECK(id=1),offset INTEGER NOT NULL);''')
        rows = [dict(event_id=f'e{i}', event_time='2026-03-01T00:00:00+00:00', service='search',
                     model='small', input_tokens=10, output_tokens=3, latency_ms=50, status='ok') for i in range(3)]
        pipeline.apply_batch(conn, rows, 100)  # Input position intentionally differs from unique row count.
    state = {'run_id': 'test-run', 'database': str(database), 'source_sha256': common.sha256(source),
             'database_sha256': common.sha256(database),
             'stats_sha256': common.sha256(common.DATA / 'gold/realtime_service.json'), 'final_offset': 100}
    report = {**state, 'source_rows': 1, 'initial_inserted': 1, 'rows_after_failure': 1,
              'failure_injected': True, 'duplicate_inserted': 0, 'offset_before': 98,
              'offset_after_failure': 98, 'recovered_inserted': 1, 'late_inserted': 1,
              'final_rows': 3, 'aggregate': common.read_json(common.DATA / 'gold/realtime_service.json')}
    common.write_json(common.DATA / 'state/latest.json', state)
    common.write_json(common.OUT / 'lab04/replay.json', report)
    return report


@pytest.fixture
def http_report(index):
    rule_question = '模拟服务的用户每周CPU推理配额是多少分钟？'
    rule = intelligence.answer(rule_question, 'public', index=index)
    stats = {'question': '查询实时服务统计', 'role': 'public', 'refused': False,
             'tool': 'service_stats', 'index_version': index['index_version'],
             'knowledge_data_version': index['source_sha256'], 'data_version': index['stats_sha256'],
             'rows': common.read_json(common.DATA / 'gold/realtime_service.json')}
    details = []
    for i in range(20):
        body = copy.deepcopy(stats if i % 5 == 0 else rule)
        body['_evidence'] = common.evidence_metadata('07', 'response')
        details.append({'request_no': i + 1, 'status': 200, 'question': body['question'], 'response': body})
    report = {'requests': 20, 'errors': 0, 'p95_ms': 1.0, 'details': details,
              'health': {'status': 'ready', 'index_version': index['index_version'],
                         'data_version': index['source_sha256'],
                         '_evidence': common.evidence_metadata('07', 'health')}}
    return common.write_json(common.OUT / 'lab07/load_test.json', report)


def test_identity_gate_accepts_seven_owned_reports_and_ignores_list_sidecars(root):
    for lab, name in REPORTS:
        common.write_json(common.OUT / f'lab{lab}' / name, {'result': 'fixture'})
    common.write_json(common.OUT / 'lab02/quarantine.json', [])
    result = governance.identity_evidence_check()
    assert len(result['reports']) == 7
    assert {r['experiment_id'] for r in result['reports']} == {lab for lab, _ in REPORTS}


@pytest.mark.parametrize('lab,name', REPORTS)
@pytest.mark.parametrize('fault', ['missing', 'wrong_student', 'unregistered', 'wrong_lab'])
def test_identity_gate_rejects_invalid_report_ownership(root, lab, name, fault):
    for item_lab, item_name in REPORTS:
        common.write_json(common.OUT / f'lab{item_lab}' / item_name, {'result': 'fixture'})
    path = common.OUT / f'lab{lab}' / name
    report = common.read_json(path)
    if fault == 'missing':
        del report['_evidence']
    elif fault == 'wrong_student':
        report['_evidence']['student_id'] = 'OTHER20260002'
    elif fault == 'unregistered':
        report['_evidence']['student_id'] = 'UNREGISTERED'
    else:
        report['_evidence']['experiment_id'] = '09'
    write_raw(path, report)
    with pytest.raises(common.IdentityError):
        governance.identity_evidence_check()


def test_replay_checks_real_apply_batch_without_equating_offset_to_rows(replay):
    before = common.sha256(replay['database'])
    result = governance.validate_replay_state()
    assert result['rows'] == 3 and result['checkpoint_offset'] == 100
    assert result['rollback_restored'] is True
    assert common.sha256(replay['database']) == before


@pytest.mark.parametrize('sql', ['DELETE FROM checkpoint', 'UPDATE checkpoint SET offset=999'])
def test_replay_rejects_missing_or_changed_checkpoint_even_with_updated_file_hash(replay, sql):
    with sqlite3.connect(replay['database']) as conn:
        conn.execute(sql)
    for path in [common.DATA / 'state/latest.json', common.OUT / 'lab04/replay.json']:
        report = common.read_json(path)
        report['database_sha256'] = common.sha256(replay['database'])
        common.write_json(path, report)
    with pytest.raises(ValueError, match='Checkpoint'):
        governance.validate_replay_state()


@pytest.mark.parametrize('field,value', [('run_id', 'another-run'), ('source_sha256', 'old-source'), ('final_offset', 99)])
def test_replay_rejects_mismatched_completed_run(replay, field, value):
    path = common.OUT / 'lab04/replay.json'
    report = common.read_json(path)
    report[field] = value
    common.write_json(path, report)
    with pytest.raises(ValueError, match='Latest/replay mismatch'):
        governance.validate_replay_state()


def test_replay_gate_detects_early_commit_in_actual_batch_function(replay, monkeypatch):
    original = pipeline.apply_batch
    def broken_batch(conn, rows, next_offset, fail_before_commit=False):
        inserted = original(conn, rows, next_offset)
        if fail_before_commit:
            raise RuntimeError('INJECTED_FAILURE_BEFORE_COMMIT')
        return inserted
    monkeypatch.setattr(governance, 'apply_batch', broken_batch)
    before = common.sha256(replay['database'])
    with pytest.raises(ValueError, match='left an event committed'):
        governance.validate_replay_state()
    assert common.sha256(replay['database']) == before


@pytest.mark.parametrize('lab', ['07', '09'])
def test_http_gate_accepts_current_business_results_for_lab_or_project(index, http_report, lab):
    http_report['health']['_evidence']['experiment_id'] = lab
    for row in http_report['details']:
        row['response']['_evidence']['experiment_id'] = lab
    result = governance.validate_http_evidence(http_report, index)
    assert result['service_experiment_id'] == lab and result['requests'] == 20


@pytest.mark.parametrize('fault', [
    'old_index', 'old_rule_source', 'old_knowledge', 'old_stats_hash', 'wrong_stats', 'wrong_answer',
    'wrong_generator', 'refused_positive', 'missing_identity', 'wrong_student', 'mixed_experiment',
    'wrong_health_student', 'wrong_health_source', 'unsupported_experiment', 'only_rules', 'leaked_hits',
])
def test_http_gate_rejects_single_invalid_business_response(index, http_report, fault):
    stats = http_report['details'][0]['response']
    rule = http_report['details'][1]['response']
    if fault == 'old_index':
        rule['index_version'] = 'obsolete-index-version'
    elif fault == 'old_rule_source':
        rule['data_version'] = 'old-source'
    elif fault == 'old_knowledge':
        stats['knowledge_data_version'] = 'old-source'
    elif fault == 'old_stats_hash':
        stats['data_version'] = 'old-stats'
    elif fault == 'wrong_stats':
        stats['rows'][0]['requests'] += 999
    elif fault == 'wrong_answer':
        rule['answer'] = '每周配额为999分钟。'
    elif fault == 'wrong_generator':
        rule['generator'] = 'ollama'
    elif fault == 'refused_positive':
        rule['refused'] = True
    elif fault == 'missing_identity':
        del rule['_evidence']
    elif fault == 'wrong_student':
        rule['_evidence']['student_id'] = 'OTHER20260002'
    elif fault == 'mixed_experiment':
        rule['_evidence']['experiment_id'] = '09'
    elif fault == 'wrong_health_student':
        http_report['health']['_evidence']['student_id'] = 'OTHER20260002'
    elif fault == 'wrong_health_source':
        http_report['health']['data_version'] = 'old-source'
    elif fault == 'unsupported_experiment':
        http_report['health']['_evidence']['experiment_id'] = '08'
    elif fault == 'leaked_hits':
        rule['hits'].append({'doc_id': 'maintenance', 'visibility': 'internal', 'text': 'private fixture'})
    else:
        for row in http_report['details']:
            row['response'] = copy.deepcopy(rule)
            row['question'] = rule['question']
    with pytest.raises(ValueError):
        governance.validate_http_evidence(http_report, index)


def test_lab08_missing_identity_fails_before_writing_release_report(root):
    (root / 'student.json').unlink()
    with pytest.raises(common.IdentityError):
        governance.lab08()
    assert not common.OUT.exists()


def test_lab08_records_frozen_evaluation_rejection(index, replay, http_report, monkeypatch):
    for lab, name in REPORTS:
        path = common.OUT / f'lab{lab}' / name
        if not path.exists():
            common.write_json(path, {'result': 'fixture'})
    calls = []
    def reject_frozen(report, index=None):
        calls.append((report, index))
        raise ValueError('Frozen code/config or positive acceptance mismatch')
    monkeypatch.setattr(intelligence, 'validate_frozen_evaluation', reject_frozen, raising=False)
    with pytest.raises(RuntimeError, match='发布检查失败'):
        governance.lab08()
    report = common.read_evidence(common.OUT / 'lab08/release_checks.json', lab='08')
    assert len(calls) == 1 and calls[0][1]['index_version'] == index['index_version']
    assert report['release_ready'] is False
    failed = [row for row in report['checks'] if not row['passed']]
    assert [row['name'] for row in failed] == ['frozen_test_evaluation']


@pytest.mark.parametrize('fault', [None, 'all_refused', 'wrong_parameters', 'changed_code_hash', 'changed_freeze'])
def test_release_gate_integrates_real_frozen_evaluation(index, replay, http_report, fault):
    for lab, name in REPORTS:
        path = common.OUT / f'lab{lab}' / name
        if not path.exists():
            common.write_json(path, {'result': 'fixture'})
    intelligence.freeze_settings()
    evaluation = intelligence.evaluate('test', 'extractive')
    if fault == 'all_refused':
        for detail in evaluation['details']:
            if detail['answerable']:
                detail['result']['refused'] = True
        evaluation['answerable_accept_rate'] = 0.0
    elif fault == 'wrong_parameters':
        evaluation['threshold'] = 2
    elif fault == 'changed_code_hash':
        evaluation['code_sha256'] = 'previous-implementation'
    elif fault == 'changed_freeze':
        path = common.OUT / 'lab06/frozen_settings.json'
        frozen = common.read_json(path)
        frozen['code_sha256'] = 'previous-implementation'
        common.write_json(path, frozen)
    common.write_json(common.OUT / 'lab06/evaluation_test_extractive.json', evaluation)
    if fault is None:
        result = governance.lab08()
        assert result['release_ready'] is True and result['passed_checks'] == result['total_checks'] == 8
    else:
        with pytest.raises(RuntimeError, match='发布检查失败'):
            governance.lab08()
        result = common.read_evidence(common.OUT / 'lab08/release_checks.json', lab='08')
        assert result['release_ready'] is False
        assert [row['name'] for row in result['checks'] if not row['passed']] == ['frozen_test_evaluation']
