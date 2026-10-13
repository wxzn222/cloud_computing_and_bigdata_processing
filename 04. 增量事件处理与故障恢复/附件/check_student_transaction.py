"""独立验证学生事务函数的正常、重放、回滚与磁盘重连路径。"""
import argparse
from contextlib import closing
import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

COURSE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COURSE_ROOT))
from coursekit.evidence import capture_callable


def state(con):
    return (con.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            con.execute("SELECT offset FROM checkpoint WHERE id=1").fetchone()[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", required=True)
    args = parser.parse_args()
    path = Path(args.module).resolve()
    spec = importlib.util.spec_from_file_location("bdp_student_transaction", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    apply = module.apply_student
    observations = []
    with tempfile.TemporaryDirectory(prefix="bdp-student-tx-") as folder:
        database = Path(folder) / "check.sqlite"
        with closing(sqlite3.connect(database)) as con:
            con.executescript("CREATE TABLE events(id TEXT PRIMARY KEY,tokens INTEGER); CREATE TABLE checkpoint(id INTEGER PRIMARY KEY,offset INTEGER); INSERT INTO checkpoint VALUES(1,0);")
            assert apply(con, [("a", 10), ("b", 20)], 2) == 2, "初次新增计数错误"
            assert state(con) == (2, 2), "正常提交状态错误"
            observations.append({"stage": "initial", "state": state(con)})
            assert apply(con, [("a", 10)], 1) == 0, "重复产生额外效果"
            assert state(con) == (2, 2), "重放让检查点倒退"
            observations.append({"stage": "replay_old", "state": state(con)})
            try:
                apply(con, [("c", 30)], 3, fail_before_commit=True)
            except RuntimeError as exc:
                assert str(exc) == "INJECTED_FAILURE_BEFORE_COMMIT", "失败类型不符合契约"
            else:
                raise AssertionError("没有真正注入并传播提交前异常")
            assert state(con) == (2, 2), "异常后数据或检查点未回滚"
            assert not con.in_transaction, "回滚后仍有未关闭事务"
            observations.append({"stage": "failed_and_rolled_back", "state": state(con)})
        with closing(sqlite3.connect(database)) as con:
            assert state(con) == (2, 2), "磁盘重开后的状态不一致"
            assert apply(con, [("c", 30)], 3) == 1, "恢复新增计数错误"
            assert apply(con, [("c", 30)], 3) == 0, "恢复后重放不幂等"
            assert state(con) == (3, 3), "最终状态错误"
            assert con.execute("SELECT SUM(tokens) FROM events").fetchone()[0] == 60, "业务总量错误"
            observations.append({"stage": "recovered_and_replayed", "state": state(con)})
    print("STUDENT_TRANSACTION_PASS")
    print(json.dumps(observations, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(capture_callable("04", "check_student_transaction", main))
