"""只读检查最近一次实验 04 的 SQLite 状态与 Gold 汇总。"""
import json
import sqlite3
import sys
from pathlib import Path

COURSE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COURSE_ROOT))
from coursekit.common import ROOT, DATA
from coursekit.evidence import capture_callable


def main():
    pointer = json.loads((DATA / "state/latest.json").read_text(encoding="utf-8"))
    database = Path(pointer["database"])
    if not database.is_absolute():
        database = (ROOT / database).resolve()
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as con:
        count = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        offset = con.execute("SELECT offset FROM checkpoint WHERE id=1").fetchone()[0]
        additions = con.execute("SELECT event_id,event_time FROM events WHERE event_id LIKE 'increment-%' ORDER BY event_id").fetchall()
        rows = con.execute("SELECT service,COUNT(*),SUM(input_tokens),SUM(output_tokens) FROM events GROUP BY service ORDER BY service").fetchall()
    summary = [dict(zip(["service", "requests", "input_tokens", "output_tokens"], row)) for row in rows]
    gold = json.loads((DATA / "gold/realtime_service.json").read_text(encoding="utf-8"))
    assert summary == gold
    assert count == sum(row["requests"] for row in gold)
    print(json.dumps({"database": str(database), "rows": count, "checkpoint": offset,
                      "additions": additions, "aggregate": summary, "matches_gold": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(capture_callable("04", "inspect_state", main))
