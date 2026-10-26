import platform
import subprocess
import sys
from pathlib import Path

import boto3
import dask
import distributed
import duckdb
import fastapi
import moto
import pyarrow

root = Path(__file__).resolve().parents[2]
raw = root / "data" / "raw" / "events.jsonl"
check = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
print(f"system={platform.system()} {platform.release()}")
print(f"python={platform.python_version()} executable={sys.executable}")
print(f"duckdb={duckdb.__version__} pyarrow={pyarrow.__version__} dask={dask.__version__}")
print(f"distributed={distributed.__version__} moto={moto.__version__} boto3={boto3.__version__}")
print(f"fastapi={fastapi.__version__}")
print(check.stdout.strip())
print(f"pip_check_exit={check.returncode}")
print(f"raw_rows={len(raw.read_text(encoding='utf-8').splitlines())} raw_bytes={raw.stat().st_size}")
assert check.returncode == 0
