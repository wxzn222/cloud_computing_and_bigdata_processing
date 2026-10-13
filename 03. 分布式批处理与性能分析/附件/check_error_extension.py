"""独立验证学生新增的错误聚合；不给出 Dask/SQL 实现。"""
import argparse
import json
import math
import sys
from pathlib import Path

COURSE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COURSE_ROOT))
from coursekit.common import DATA, OUT
from coursekit.evidence import capture_callable


def main():
    import pyarrow.parquet as pq

    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=int, default=2000)
    args = parser.parse_args()
    result = json.loads((OUT / f"lab03/student-latency-{args.threshold}.json").read_text(encoding="utf-8"))
    expected = {}
    for row in pq.read_table(DATA / "silver/events.parquet", columns=["service", "status"]).to_pylist():
        service = row["service"]
        tally = expected.setdefault(service, {"requests": 0, "errors": 0})
        tally["requests"] += 1
        if row["status"] == "error":
            tally["errors"] += 1
    actual = {row["service"]: row for row in result["aggregate"]}
    assert set(actual) == set(expected), "服务集合不一致"
    for service, tally in expected.items():
        row = actual[service]
        assert "errors" in row and "error_rate" in row, "缺少 errors/error_rate，请先完成独立编码"
        assert row["requests"] == tally["requests"], "分母不是全部合法请求"
        assert row["errors"] == tally["errors"], "错误计数不一致"
        assert math.isclose(row["error_rate"], tally["errors"] / tally["requests"], rel_tol=1e-12, abs_tol=1e-12), "错误率不一致"
    print("ERROR_EXTENSION_PASS", {"total_errors": sum(row["errors"] for row in actual.values())})


if __name__ == "__main__":
    raise SystemExit(capture_callable("03", "check_error_extension", main))
