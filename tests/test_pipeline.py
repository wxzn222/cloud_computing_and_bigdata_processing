import sqlite3
import json
import pytest
from coursekit import common, pipeline
from coursekit.pipeline import validate_event, apply_batch


def sample(**updates):
    return {**dict(event_id='e1', event_time='2026-03-01T00:00:00+00:00', service='search',
                   model='small', input_tokens=10, output_tokens=3, latency_ms=50, status='ok'), **updates}


@pytest.fixture
def db(tmp_path):
    conn = sqlite3.connect(tmp_path / 'events.sqlite')
    conn.executescript('''CREATE TABLE events(event_id TEXT PRIMARY KEY,event_time TEXT,service TEXT,
        model TEXT,input_tokens INTEGER,output_tokens INTEGER,latency_ms INTEGER,status TEXT);
        CREATE TABLE checkpoint(id INTEGER PRIMARY KEY,offset INTEGER);''')
    yield conn
    conn.close()


def test_contract_rejects_bool_and_naive_timestamp():
    row = sample()
    assert validate_event(row) is None
    row['input_tokens'] = True
    assert validate_event(row) == 'invalid_input_tokens'
    row['input_tokens'] = 10
    row['event_time'] = '2026-03-01T00:00:00'
    assert validate_event(row) == 'non_utc_time'


def test_replay_effect_and_checkpoint_are_atomic(db):
    assert apply_batch(db, [sample()], 1) == 1
    assert apply_batch(db, [sample()], 1) == 0
    next_row = {**sample(), 'event_id': 'e2'}
    with pytest.raises(RuntimeError, match='INJECTED'):
        apply_batch(db, [next_row], 2, fail_before_commit=True)
    assert db.execute('SELECT COUNT(*) FROM events').fetchone()[0] == 1
    assert db.execute('SELECT offset FROM checkpoint').fetchone()[0] == 1
    assert apply_batch(db, [next_row], 2) == 1


def test_conflicting_duplicate_cannot_silently_change_a_fact(db):
    apply_batch(db, [sample()], 1)
    with pytest.raises(ValueError, match='Conflicting'):
        apply_batch(db, [{**sample(), 'input_tokens': 999}], 2)
    assert db.execute('SELECT input_tokens FROM events').fetchone()[0] == 10
    assert db.execute('SELECT offset FROM checkpoint').fetchone()[0] == 1


@pytest.fixture
def course_root(tmp_path, monkeypatch):
    monkeypatch.setenv('BDP_ROOT', str(tmp_path))
    monkeypatch.setattr(common, 'ROOT', tmp_path)
    monkeypatch.setattr(common, 'DATA', tmp_path / 'data')
    monkeypatch.setattr(common, 'OUT', tmp_path / 'outputs')
    monkeypatch.setattr(common, '_WRITTEN', {})
    monkeypatch.setattr(pipeline, 'DATA', common.DATA)
    monkeypatch.setattr(pipeline, 'OUT', common.OUT)
    monkeypatch.setattr(pipeline, 'emit', lambda lab, stage, value: value)
    common.write_json(tmp_path / 'student.json', {'student_id': 'TEST20260001'})
    return tmp_path


@pytest.mark.parametrize('name', ['seed', 'lab01', 'lab02', 'lab03', 'lab04'])
def test_missing_identity_fails_before_creating_any_pipeline_artifact(course_root, name):
    (course_root / 'student.json').unlink()
    with pytest.raises(common.IdentityError):
        getattr(pipeline, name)()
    assert list(course_root.iterdir()) == []


def test_accepted_iso_formats_share_one_daily_bucket(course_root):
    pq = pytest.importorskip('pyarrow.parquet')
    pytest.importorskip('duckdb')
    rows = [sample(event_time='2026-03-01T00:00:05+00:00'),
            sample(event_time='20260301T000005+00:00'),  # Same fact, different representation.
            sample(event_id='e2', event_time='20260301T000005+00:00'),
            sample(event_id='e3', event_time='2026-W09-7T00:00:05+00:00')]
    assert all(validate_event(row) is None for row in rows)
    source = common.DATA / 'raw/events.jsonl'
    source.parent.mkdir(parents=True)
    source.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    common.write_json(common.OUT / 'lab01/storage.json', {'source_sha256': common.sha256(source)})
    result = pipeline.lab02()
    assert result['valid_unique'] == 3 and result['duplicate_rows'] == 1
    assert pq.read_table(common.DATA / 'gold/service_daily.parquet').to_pylist() == [
        {'day': '2026-03-01', 'service': 'search', 'requests': 3, 'input_tokens': 30, 'output_tokens': 9}]
    stored = pq.read_table(common.DATA / 'silver/events.parquet').to_pylist()
    assert {row['event_time'] for row in stored} == {'2026-03-01T00:00:05+00:00'}


def test_lab04_avoids_existing_demo_ids_and_preserves_repeated_runs(course_root):
    pa = pytest.importorskip('pyarrow')
    pq = pytest.importorskip('pyarrow.parquet')
    existing = {'increment-new', 'increment-new-1', 'increment-late', 'increment-late-1'}
    source = common.DATA / 'silver/events.parquet'
    source.parent.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist([sample(event_id=key) for key in sorted(existing)]), source)
    common.write_json(common.OUT / 'lab03/benchmark.json', {'silver_sha256': common.sha256(source)})
    first = pipeline.lab04()
    assert first['recovered_inserted'] == first['late_inserted'] == 1
    assert first['final_rows'] == len(existing) + 2
    assert not (set(first['demo_event_ids'].values()) & existing)
    with sqlite3.connect(first['database']) as conn:
        assert {row[0] for row in conn.execute('SELECT event_id FROM events')} == existing | set(first['demo_event_ids'].values())
        assert conn.execute('SELECT offset FROM checkpoint').fetchone()[0] == first['final_offset']
    second = pipeline.lab04()
    assert second['run_id'] != first['run_id']
    assert second['aggregate'] == first['aggregate']
    assert common.sha256(first['database']) == first['database_sha256']
    latest = common.read_json(common.DATA / 'state/latest.json')
    assert latest['database_sha256'] == second['database_sha256']
    assert latest['final_offset'] == second['final_offset']


@pytest.mark.parametrize('offset', [-1, True, 1.5, '2'])
def test_invalid_checkpoint_offset_cannot_commit_events(db, offset):
    with pytest.raises(ValueError, match='next_offset'):
        apply_batch(db, [sample()], offset)
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 0
    assert db.execute('SELECT count(*) FROM checkpoint').fetchone()[0] == 0
