"""个人 Dask 聚合：修改慢请求阈值，并用独立 SQL 核对。"""
import json
import os
import sys
from pathlib import Path

COURSE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COURSE_ROOT))
from coursekit.common import DATA, OUT, write_json
from coursekit.evidence import capture_callable

SLOW_MS = 1000  # 本人改为 2000；运行前写下预测。


def main():
    import dask.dataframe as dd
    import duckdb
    from distributed import Client, LocalCluster

    source = DATA / "silver/events.parquet"
    with LocalCluster(n_workers=2, threads_per_worker=1, processes=True,
                      memory_limit="1GiB", host="127.0.0.1", dashboard_address=None) as cluster:
        with Client(cluster) as client:
            df = dd.read_parquet(str(source)).repartition(npartitions=8)
            df = df.assign(is_slow=(df["latency_ms"] >= SLOW_MS).astype("int64"))
            actual = df.groupby("service").agg({"event_id": "count", "latency_ms": "sum", "is_slow": "sum"}).compute()
            actual = actual.reset_index().rename(columns={"event_id": "requests", "latency_ms": "latency_ms_sum", "is_slow": "slow_requests"})
            actual = actual.sort_values("service").reset_index(drop=True)
            pids = client.run(os.getpid)
    with duckdb.connect() as con:
        expected = con.execute("""SELECT service,COUNT(*)::BIGINT AS requests,
            SUM(latency_ms)::BIGINT AS latency_ms_sum,
            SUM(CASE WHEN latency_ms >= ? THEN 1 ELSE 0 END)::BIGINT AS slow_requests
            FROM read_parquet(?) GROUP BY service ORDER BY service""", [SLOW_MS, str(source)]).fetchdf()
    assert actual.to_dict(orient="records") == expected.to_dict(orient="records")
    actual["mean_latency_ms"] = actual["latency_ms_sum"] / actual["requests"]
    actual["slow_rate"] = actual["slow_requests"] / actual["requests"]
    result = {"slow_ms": SLOW_MS, "worker_pids": pids, "matches_sql": True,
              "aggregate": actual.to_dict(orient="records")}
    target = OUT / f"lab03/student-latency-{SLOW_MS}.json"
    result = write_json(target, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(capture_callable("03", "student_latency", main))
