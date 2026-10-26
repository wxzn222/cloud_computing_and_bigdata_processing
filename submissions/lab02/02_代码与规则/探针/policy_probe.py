import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'coursekit').is_dir())
sys.path.insert(0, str(ROOT))
from coursekit.pipeline import validate_event


def probe(case):
    row = {'event_id': 'probe', 'event_time': '2026-03-01T12:00:00+00:00',
           'service': 'assistant', 'model': 'small', 'input_tokens': 100,
           'output_tokens': 20, 'latency_ms': 150, 'status': 'ok'}
    if case == 'boolean':
        row['input_tokens'] = True
    elif case == 'string':
        row['input_tokens'] = '100'
    elif case == 'negative':
        row['input_tokens'] = -1
    elif case == 'naive_time':
        row['event_time'] = '2026-03-01T12:00:00'
    return row, validate_event(row)


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if case == 'all':
        results = {name: (probe(name)[1] or 'accepted') for name in
                   ['boolean', 'string', 'integer', 'negative', 'naive_time']}
        print(json.dumps(results, ensure_ascii=False, indent=2))
        assert results['boolean'] == results['string'] == 'invalid_input_tokens'
        assert results['integer'] == 'accepted' and results['naive_time'] == 'non_utc_time'
        return 0
    row, reason = probe(case)
    expect = sys.argv[2] if len(sys.argv) > 2 else 'reject'
    print(json.dumps({'case': case, 'input_tokens': row['input_tokens'],
                      'reason': reason or 'accepted'}, ensure_ascii=False, indent=2))
    ok = (reason is None) if expect == 'accept' else (reason is not None)
    if not ok:
        print(f'EXPECTED_{expect.upper()}_BUT_GOT_{reason or accepted}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
