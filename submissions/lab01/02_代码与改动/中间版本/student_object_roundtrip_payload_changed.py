"""实验 01 个人练习：修改 make_key，再验证内容与对象地址的区别。"""
import hashlib
import json
import sys
from pathlib import Path

COURSE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COURSE_ROOT))
from coursekit.common import require_identity
from coursekit.evidence import capture_callable

STUDENT_ID = None  # main 从当前课程登记记录读取；个人练习只修改 make_key。


def make_key():
    # 独立改动：将共享前缀改为含自己学号的前缀，保留文件后缀。
    return "students/2410311411/raw/demo.json"


def main():
    global STUDENT_ID
    STUDENT_ID = require_identity()
    import boto3
    from moto.server import ThreadedMotoServer

    payload = json.dumps({"requests": 4, "tokens": 120}, sort_keys=True).encode("utf-8")
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    try:
        host, port = server.get_host_and_port()
        client = boto3.client(
            "s3", endpoint_url=f"http://{host}:{port}", region_name="us-east-1",
            aws_access_key_id="testing", aws_secret_access_key="testing",
        )
        client.create_bucket(Bucket="bdp-student-demo")
        key = make_key()
        client.put_object(Bucket="bdp-student-demo", Key=key, Body=payload)
        received = client.get_object(Bucket="bdp-student-demo", Key=key)["Body"].read()
        source_hash = hashlib.sha256(payload).hexdigest()
        downloaded_hash = hashlib.sha256(received).hexdigest()
        assert source_hash == downloaded_hash
        print(json.dumps({"student_id": STUDENT_ID, "key": key,
                          "source_sha256": source_hash, "downloaded_sha256": downloaded_hash,
                          "equal": source_hash == downloaded_hash}, ensure_ascii=False, indent=2))
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(capture_callable("01", "student_object_roundtrip", main))
