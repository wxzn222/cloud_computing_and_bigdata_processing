"""故意保留提前提交错误的个人练习；改为 False 后应满足原子性契约。"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

COURSE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COURSE_ROOT))
from coursekit.common import OUT, write_json
from coursekit.evidence import capture_callable

COMMIT_EARLY = True  # 本人改为 False；先预测失败后的行数与检查点。


def apply(con, fail=False):
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT OR IGNORE INTO events VALUES ('event-x',100)")
        if COMMIT_EARLY:
            con.commit()  # 教学故障：数据在检查点之前独立生效，之后 rollback 无法撤销。
        if fail:
            raise RuntimeError("INJECTED_BEFORE_CHECKPOINT")
        con.execute("UPDATE checkpoint SET offset=1 WHERE id=1")
        con.commit()
    except Exception:
        con.rollback()
        raise


def main():
    with tempfile.TemporaryDirectory(prefix="bdp-atomicity-") as folder:
        path = Path(folder) / "exercise.sqlite"
        con = sqlite3.connect(path)
        con.executescript("CREATE TABLE events(id TEXT PRIMARY KEY,tokens INTEGER); CREATE TABLE checkpoint(id INTEGER PRIMARY KEY,offset INTEGER); INSERT INTO checkpoint VALUES(1,0);")
        try:
            apply(con, fail=True)
        except RuntimeError as exc:
            assert str(exc) == "INJECTED_BEFORE_CHECKPOINT"
        rows_after_failure = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        offset_after_failure = con.execute("SELECT offset FROM checkpoint").fetchone()[0]
        con.close()
        con = sqlite3.connect(path)
        apply(con)
        apply(con)  # 重复投递同一 ID，不应产生两行。
        final_rows = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        final_offset = con.execute("SELECT offset FROM checkpoint").fetchone()[0]
        con.close()
    result = {"commit_early": COMMIT_EARLY, "rows_after_failure": rows_after_failure,
              "offset_after_failure": offset_after_failure,
              "atomic_contract_passed": rows_after_failure == 0 and offset_after_failure == 0,
              "final_rows": final_rows, "final_offset": final_offset}
    assert final_rows == 1 and final_offset == 1
    label = "early" if COMMIT_EARLY else "atomic"
    target = OUT / f"lab04/student-atomicity-{label}.json"
    result = write_json(target, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(capture_callable("04", "student_atomicity", main))
