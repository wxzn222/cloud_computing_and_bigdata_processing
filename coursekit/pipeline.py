"""Labs 01–04. Functions deliberately expose the contracts taught in the manuals."""
import hashlib
import json
import math
import random
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .common import DATA, OUT, emit, read_evidence, read_json, require_identity, sha256, write_json


def seed(rows=20000):
    """Deterministic data; refuses to silently overwrite a modified raw file."""
    require_identity()
    if rows < 100:
        raise ValueError('rows must be >= 100')
    rng = random.Random(42)
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    events = []
    for i in range(rows):
        service = rng.choices(['assistant', 'search', 'batch'], weights=[7, 2, 1])[0]
        events.append({
            'event_id': f'evt-{i:08d}', 'event_time': (start + timedelta(seconds=i * 5)).isoformat(),
            'service': service, 'model': rng.choice(['small', 'medium']),
            'input_tokens': rng.randint(20, 1800), 'output_tokens': rng.randint(10, 600),
            'latency_ms': rng.randint(80, 4000), 'status': 'error' if i % 25 == 0 else 'ok',
        })
    records = events + events[:100] + [
        {**events[0], 'event_id': 'bad-negative', 'input_tokens': -1},
        {**events[1], 'event_id': 'bad-time', 'event_time': 'not-a-time'},
    ]
    path = DATA / 'raw/events.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    content = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records)
    if path.exists() and path.read_text(encoding='utf-8') != content:
        raise FileExistsError('raw/events.jsonl already differs. Use a new BDP_ROOT for a different scale; never overwrite evidence.')
    path.write_text(content, encoding='utf-8')
    from .intelligence import seed_corpus
    seed_corpus()
    result = {'valid_unique': rows, 'duplicates': 100, 'invalid': 2, 'raw_rows': len(records), 'sha256': sha256(path), 'seed': 42}
    write_json(DATA / 'manifests/raw.json', result)
    return emit('00', 'seed', result)


def require(path, prior):
    if not Path(path).exists():
        raise FileNotFoundError(f'Missing {path}; complete {prior} first.')


def lab01(endpoint=None):
    """A real HTTP SDK roundtrip against a clearly labelled cloud API emulator."""
    require_identity()
    import boto3
    from botocore.config import Config
    from moto.server import ThreadedMotoServer
    source = DATA / 'raw/events.jsonl'
    require(source, 'seed')
    server = None
    if endpoint:
        parsed = urlparse(endpoint)
        if parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.scheme != 'http':
            raise ValueError('The teaching endpoint must be local HTTP; no real cloud credentials are used.')
    else:
        server = ThreadedMotoServer(ip_address='127.0.0.1', port=0, verbose=False)
        server.start()
        host, port = server.get_host_and_port()
        endpoint = f'http://{host}:{port}'
    try:
        s3 = boto3.client('s3', endpoint_url=endpoint, region_name='us-east-1',
                          aws_access_key_id='teaching-only', aws_secret_access_key='teaching-only',
                          config=Config(s3={'addressing_style': 'path'}, retries={'max_attempts': 2}))
        bucket = 'bdp-teaching'
        if bucket not in [x['Name'] for x in s3.list_buckets()['Buckets']]:
            s3.create_bucket(Bucket=bucket)
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={'Status': 'Enabled'})
        key = 'bronze/events/' + sha256(source) + '.jsonl'
        first = s3.put_object(Bucket=bucket, Key=key, Body=source.read_bytes())
        second = s3.put_object(Bucket=bucket, Key=key, Body=source.read_bytes())
        saved = OUT / 'lab01/downloaded-events.jsonl'
        saved.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, key, str(saved))
        receipt = {
            'endpoint': endpoint, 'backend': 'Moto S3 API emulator; volatile memory, not durable cloud storage',
            'bucket': bucket, 'key': key, 'bytes': source.stat().st_size,
            'source_sha256': sha256(source), 'download_sha256': sha256(saved),
            'hash_matches': sha256(source) == sha256(saved),
            'version_ids_differ': first['VersionId'] != second['VersionId'],
        }
        assert receipt['hash_matches'] and receipt['version_ids_differ']
        write_json(OUT / 'lab01/storage.json', receipt)
        return emit('01', 'verify', receipt)
    finally:
        if server:
            server.stop()


def validate_event(row):
    """Independent task: change ONE contract and explain downstream effects."""
    fields = ['event_id', 'event_time', 'service', 'model', 'input_tokens', 'output_tokens', 'latency_ms', 'status']
    if any(key not in row for key in fields):
        return 'missing_field'
    if not isinstance(row['event_id'], str) or not row['event_id']:
        return 'invalid_event_id'
    for key in ['input_tokens', 'output_tokens', 'latency_ms']:
        if type(row[key]) is not int or row[key] < 0:
            return f'invalid_{key}'
    if row['service'] not in ['assistant', 'search', 'batch'] or row['model'] not in ['small', 'medium']:
        return 'invalid_category'
    if row['status'] not in ['ok', 'error']:
        return 'invalid_status'
    try:
        stamp = datetime.fromisoformat(row['event_time'])
        if stamp.utcoffset() != timedelta(0):
            return 'non_utc_time'
    except (ValueError, TypeError):
        return 'invalid_event_time'
    return None


def lab02():
    require_identity()
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    source = DATA / 'raw/events.jsonl'
    require(source, 'seed / lab01')
    require(OUT / 'lab01/storage.json', 'lab01')
    if read_evidence(OUT / 'lab01/storage.json', lab='01')['source_sha256'] != sha256(source):
        raise ValueError('Raw data changed after lab01; rerun the storage verification before lab02.')
    unique, rejected, duplicates = {}, [], 0
    for line_no, line in enumerate(source.read_text(encoding='utf-8').splitlines(), start=1):
        try:
            row = json.loads(line)
            reason = validate_event(row) if isinstance(row, dict) else 'not_an_object'
        except json.JSONDecodeError:
            row, reason = {'raw_line': line}, 'invalid_json'
        if not reason:
            # All UTC formats accepted by the contract have one stored representation.
            # Normalize before deduplication, so equivalent timestamps describe one fact.
            row = {**row, 'event_time': datetime.fromisoformat(row['event_time']).isoformat()}
        if reason:
            rejected.append({'line': line_no, 'reason': reason, 'record': row})
        elif row['event_id'] in unique:
            if unique[row['event_id']] != row:
                raise ValueError(f'Conflicting event_id {row["event_id"]}: define a correction policy before continuing.')
            duplicates += 1
        else:
            unique[row['event_id']] = row
    if not unique:
        raise ValueError('No valid data; review the contract rather than publishing an empty release.')
    table = pa.Table.from_pylist(list(unique.values()))
    silver = DATA / 'silver/events.parquet'
    silver.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, silver, compression='zstd', row_group_size=4096)
    with duckdb.connect() as con:
        con.register('events', table)
        summary = con.execute('''SELECT service, COUNT(*) AS requests,
          SUM(input_tokens)::BIGINT AS input_tokens, SUM(output_tokens)::BIGINT AS output_tokens,
          SUM(latency_ms)::BIGINT AS latency_ms_sum,
          SUM(CASE WHEN status='error' THEN 1 ELSE 0 END)::BIGINT AS errors
          FROM events GROUP BY service ORDER BY service''').fetchdf()
        daily = con.execute('''SELECT CAST(CAST(event_time AS TIMESTAMP) AS DATE)::VARCHAR AS day, service,
          COUNT(*) AS requests, SUM(input_tokens)::BIGINT AS input_tokens,
          SUM(output_tokens)::BIGINT AS output_tokens
          FROM events GROUP BY day, service ORDER BY day, service''').fetch_arrow_table()
        plan = con.execute('EXPLAIN ANALYZE SELECT SUM(input_tokens) FROM read_parquet(?) WHERE service=?',
                           [str(silver), 'search']).fetchall()
    gold = DATA / 'gold/service_daily.parquet'
    gold.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(daily, gold, compression='zstd')
    quality = {'raw_rows': len(unique) + duplicates + len(rejected), 'valid_unique': len(unique),
               'duplicate_rows': duplicates, 'rejected_rows': len(rejected),
               'conservation': len(unique) + duplicates + len(rejected),
               'raw_bytes': source.stat().st_size, 'parquet_bytes': silver.stat().st_size,
               'aggregate': summary.to_dict(orient='records')}
    write_json(OUT / 'lab02/quality.json', quality)
    write_json(OUT / 'lab02/quarantine.json', rejected)
    (OUT / 'lab02/query-plan.txt').write_text('\n'.join(str(x) for x in plan), encoding='utf-8')
    write_json(DATA / 'manifests/silver.json', {'source_sha256': sha256(source),
               'silver_sha256': sha256(silver), 'rows': len(unique), 'schema': str(table.schema),
               'contract_version': 2, 'gold_sha256': sha256(gold),
               'time_policy': 'parse accepted UTC ISO timestamps and store canonical datetime.isoformat()'})
    return emit('02', 'verify', quality)


def lab03(workers=2, partitions=8):
    require_identity()
    import duckdb
    import dask.dataframe as dd
    from distributed import Client, LocalCluster
    silver = DATA / 'silver/events.parquet'
    require(silver, 'lab02')
    if workers not in [1, 2, 3, 4] or not 1 <= partitions <= 64:
        raise ValueError('Teaching limits: 1-4 workers, 1-64 partitions.')
    if sha256(silver) != read_json(DATA / 'manifests/silver.json')['silver_sha256']:
        raise ValueError('Silver hash mismatch; rerun lab02 with the intended input.')
    baseline_start = time.perf_counter()
    with duckdb.connect() as con:
        baseline = con.execute('''SELECT service, COUNT(*)::BIGINT AS requests,
            SUM(input_tokens)::BIGINT AS input_tokens, SUM(output_tokens)::BIGINT AS output_tokens,
            SUM(latency_ms)::BIGINT AS latency_ms_sum
            FROM read_parquet(?) GROUP BY service ORDER BY service''', [str(silver)]).fetchdf()
    duckdb_s = time.perf_counter() - baseline_start
    started = time.perf_counter()
    with LocalCluster(n_workers=workers, threads_per_worker=1, processes=True,
                      memory_limit='1GiB', host='127.0.0.1', dashboard_address=None) as cluster:
        with Client(cluster) as client:
            startup_s = time.perf_counter() - started
            df = dd.read_parquet(str(silver)).repartition(npartitions=partitions)
            # Explicit hash exchange: records with the same service meet at one partition.
            shuffled = df.shuffle(on='service', shuffle_method='tasks')
            group = shuffled.groupby('service').agg({
                'event_id': 'count', 'input_tokens': 'sum', 'output_tokens': 'sum', 'latency_ms': 'sum'})
            compute_started = time.perf_counter()
            actual = group.compute().reset_index().rename(columns={'event_id': 'requests', 'latency_ms': 'latency_ms_sum'})
            compute_s = time.perf_counter() - compute_started
            actual = actual.sort_values('service')[baseline.columns].reset_index(drop=True)
            partition_rows = shuffled.map_partitions(len).compute().tolist()
            info = client.scheduler_info()
            worker_pids = client.run(__import__('os').getpid)
            task_count = len(group.__dask_graph__())
    rows = actual.to_dict(orient='records')
    equal = rows == baseline.to_dict(orient='records')
    assert equal, 'Parallel answer differs from SQL oracle.'
    result = {'workers': workers, 'partitions': partitions, 'worker_pids': worker_pids,
              'scheduler_workers': len(info['workers']), 'task_count': task_count,
              'partition_rows_after_shuffle': partition_rows, 'matches_duckdb': equal,
              'duckdb_seconds': duckdb_s, 'startup_seconds': startup_s, 'compute_seconds': compute_s,
              'total_seconds': time.perf_counter() - started, 'silver_sha256': sha256(silver),
              'aggregate': rows, 'timing_note': 'total includes separate partition diagnostics; do not claim linear speedup'}
    write_json(OUT / f'lab03/benchmark-w{workers}-p{partitions}.json', result)
    write_json(OUT / 'lab03/benchmark.json', result)
    return emit('03', 'verify', result)


EVENT_FIELDS = ['event_id', 'event_time', 'service', 'model', 'input_tokens', 'output_tokens', 'latency_ms', 'status']


def unused_event_id(prefix, existing_ids):
    """Choose a deterministic demonstration ID without reserving input namespaces."""
    candidate, suffix = prefix, 0
    while candidate in existing_ids:
        suffix += 1
        candidate = f'{prefix}-{suffix}'
    return candidate


def apply_batch(con, rows, next_offset, fail_before_commit=False):
    """One SQLite transaction covers the data effect and its checkpoint."""
    if type(next_offset) is not int or next_offset < 0:
        raise ValueError('next_offset must be a nonnegative integer')
    before = con.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    try:
        con.execute('BEGIN IMMEDIATE')
        for row in rows:
            reason = validate_event(row)
            if reason:
                raise ValueError(f'Invalid stream event: {reason}')
            old = con.execute('SELECT * FROM events WHERE event_id=?', (row['event_id'],)).fetchone()
            values = tuple(row[key] for key in EVENT_FIELDS)
            if old and old != values:
                raise ValueError('Conflicting duplicate event_id; correction policy is required.')
            con.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?)', values)
        con.execute('INSERT INTO checkpoint VALUES (1,?) ON CONFLICT(id) DO UPDATE SET offset=MAX(offset,excluded.offset)', (next_offset,))
        if fail_before_commit:
            raise RuntimeError('INJECTED_FAILURE_BEFORE_COMMIT')
        con.commit()
    except Exception:
        con.rollback()
        raise
    return con.execute('SELECT COUNT(*) FROM events').fetchone()[0] - before


def lab04():
    require_identity()
    import pyarrow.parquet as pq
    silver = DATA / 'silver/events.parquet'
    require(silver, 'lab02 and lab03')
    require(OUT / 'lab03/benchmark.json', 'lab03')
    source_hash = sha256(silver)
    if read_evidence(OUT / 'lab03/benchmark.json', lab='03')['silver_sha256'] != source_hash:
        raise ValueError('Silver data changed after lab03; recompute the batch oracle first.')
    source_rows = pq.read_table(silver).to_pylist()
    if not source_rows:
        raise ValueError('No stream input; run lab02 with valid data first.')
    existing_ids = {row['event_id'] for row in source_rows}
    fresh_id = unused_event_id('increment-new', existing_ids)
    existing_ids.add(fresh_id)
    late_id = unused_event_id('increment-late', existing_ids)
    # A new run directory preserves all previous experiments, including failure evidence.
    run_id = uuid.uuid4().hex[:12]
    db_path = DATA / f'state/runs/{run_id}/events.sqlite'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as con:
        con.executescript('''CREATE TABLE events(event_id TEXT PRIMARY KEY, event_time TEXT NOT NULL,
      service TEXT NOT NULL, model TEXT NOT NULL, input_tokens INTEGER NOT NULL,
      output_tokens INTEGER NOT NULL, latency_ms INTEGER NOT NULL, status TEXT NOT NULL);
      CREATE TABLE checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), offset INTEGER NOT NULL);''')
        inserted = 0
        for start in range(0, len(source_rows), 500):
            batch = source_rows[start:start + 500]
            inserted += apply_batch(con, batch, start + len(batch))
        repeated = apply_batch(con, source_rows[:100], len(source_rows))
        offset_before = con.execute('SELECT offset FROM checkpoint').fetchone()[0]
        fresh = {**source_rows[-1], 'event_id': fresh_id}
        failed = False
        try:
            apply_batch(con, [fresh], len(source_rows) + 1, fail_before_commit=True)
        except RuntimeError as error:
            failed = str(error) == 'INJECTED_FAILURE_BEFORE_COMMIT'
        after_failure = con.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        offset_after_failure = con.execute('SELECT offset FROM checkpoint').fetchone()[0]
    # Reopen from disk: recovery uses durable state, not a surviving Python collection.
    with closing(sqlite3.connect(db_path)) as con:
        recovered = apply_batch(con, [fresh], len(source_rows) + 1)
        late = {**source_rows[0], 'event_id': late_id,
                'event_time': '2026-02-28T23:59:00+00:00'}
        late_inserted = apply_batch(con, [late], len(source_rows) + 2)
        agg = con.execute('''SELECT service,COUNT(*),SUM(input_tokens),SUM(output_tokens)
                         FROM events GROUP BY service ORDER BY service''').fetchall()
        total = con.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        final_offset = con.execute('SELECT offset FROM checkpoint').fetchone()[0]
    assert failed and inserted == len(source_rows) and repeated == 0
    assert after_failure == len(source_rows) and offset_before == offset_after_failure
    assert recovered == 1 and late_inserted == 1 and total == len(source_rows) + 2
    summary = [dict(zip(['service', 'requests', 'input_tokens', 'output_tokens'], row)) for row in agg]
    write_json(DATA / 'gold/realtime_service.json', summary)
    state = {'run_id': run_id, 'database': str(db_path), 'source_sha256': source_hash,
             'database_sha256': sha256(db_path), 'stats_sha256': sha256(DATA / 'gold/realtime_service.json'),
             'final_offset': final_offset}
    result = {**state, 'source_rows': len(source_rows),
              'demo_event_ids': {'recovered': fresh_id, 'late': late_id},
              'initial_inserted': inserted, 'duplicate_inserted': repeated, 'failure_injected': failed,
              'rows_after_failure': after_failure, 'offset_before': offset_before,
              'offset_after_failure': offset_after_failure, 'recovered_inserted': recovered,
              'late_inserted': late_inserted, 'final_rows': total, 'final_offset': final_offset,
              'late_policy': 'accept and recompute historical aggregate; no watermark implemented',
              'aggregate': summary, 'semantics': 'single-database transactional effect with event_id deduplication; not global exactly-once'}
    write_json(OUT / 'lab04/replay.json', result)
    # Publish the pointer last: it must refer to a completed report and database.
    write_json(DATA / 'state/latest.json', state)
    return emit('04', 'verify', result)
