"""个人质量契约实验：只写个人结果，不改写课程 Silver。"""
import json
import sys
from pathlib import Path

# 向上查找课程根目录，归档后移动到任意子目录仍可运行。
COURSE_ROOT = next(path for path in Path(__file__).resolve().parents if (path / coursekit).is_dir())
sys.path.insert(0, str(COURSE_ROOT))
from coursekit.common import DATA, OUT, write_json
from coursekit.evidence import capture_callable

MAX_INPUT_TOKENS = 1200  # 本人将它改为 1200，先预测再运行。


def policy(row):
    from coursekit.pipeline import validate_event

    reason = validate_event(row)
    if reason is not None:
        return reason
    if row["input_tokens"] > MAX_INPUT_TOKENS:
        return "policy_input_limit"
    return None


def main():
    records = [json.loads(line) for line in (DATA / "raw/events.jsonl").read_text(encoding="utf-8").splitlines()]
    kept, rejected, duplicates = {}, {}, 0
    for row in records:
        reason = policy(row)
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
        elif row["event_id"] in kept:
            if kept[row["event_id"]] != row:
                raise ValueError("conflicting duplicate")
            duplicates += 1
        else:
            kept[row["event_id"]] = row
    probes = {
        "negative": {**records[0], "input_tokens": -1},
        "boolean": {**records[0], "input_tokens": True},
        "naive_time": {**records[0], "event_time": "2026-03-01T12:00:00"},
    }
    result = {
        "max_input_tokens": MAX_INPUT_TOKENS, "raw_rows": len(records),
        "valid_unique": len(kept), "duplicates": duplicates, "rejected_by_reason": rejected,
        "input_tokens_sum": sum(row["input_tokens"] for row in kept.values()),
        "probe_errors": {name: policy(row) for name, row in probes.items()},
    }
    assert len(records) == len(kept) + duplicates + sum(rejected.values())
    target = OUT / f"lab02/student-policy-{MAX_INPUT_TOKENS}.json"
    result = write_json(target, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(capture_callable("02", "student_quality_policy", main))
