"""从课程根目录运行，核对 Silver 与 Gold 总量。"""
from pathlib import Path
import sys

COURSE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COURSE_ROOT))
from coursekit.common import DATA
from coursekit.evidence import capture_callable


def main():
    import duckdb

    with duckdb.connect() as con:
        silver = str(DATA / "silver/events.parquet")
        gold = str(DATA / "gold/service_daily.parquet")
        print(con.execute("SELECT * FROM read_parquet(?) ORDER BY day,service", [gold]).fetchdf().to_string(index=False))
        before = con.execute("SELECT COUNT(*),SUM(input_tokens),SUM(output_tokens) FROM read_parquet(?)", [silver]).fetchone()
        after = con.execute("SELECT SUM(requests),SUM(input_tokens),SUM(output_tokens) FROM read_parquet(?)", [gold]).fetchone()
        assert before == after
        print({"silver_totals": before, "gold_totals": after, "totals_match": True})


if __name__ == "__main__":
    raise SystemExit(capture_callable("02", "inspect_gold", main))
