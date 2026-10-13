"""Run shipped entrypoints in isolated layouts, using only the standard library."""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from coursekit import common


REPOSITORY = Path(__file__).resolve().parents[1]
LAB_DIRS = {
    "01": "01. 云端数据接口与可复现环境",
    "02": "02. 数据湖与质量契约",
    "03": "03. 分布式批处理与性能分析",
    "04": "04. 增量事件处理与故障恢复",
}
ENTRYPOINTS = [
    ("01", "student_object_roundtrip.py"),
    ("02", "student_quality_policy.py"),
    ("02", "inspect_gold.py"),
    ("03", "student_latency_aggregate.py"),
    ("03", "check_error_extension.py"),
    ("04", "student_atomicity.py"),
    ("04", "inspect_state.py"),
    ("04", "check_student_transaction.py"),
]
STUDENT = "SCRIPT-20260042"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    checkout, data_root = tmp_path / "checkout", tmp_path / "isolated-data"
    # Copy executable source, never repository data or generated output. A path
    # regression therefore writes only inside this test's temporary checkout.
    shutil.copytree(REPOSITORY / "coursekit", checkout / "coursekit",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for directory in LAB_DIRS.values():
        for source in (REPOSITORY / directory / "附件").glob("*.py"):
            target = checkout / directory / "附件" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    monkeypatch.setattr(common, "ROOT", data_root)
    monkeypatch.setattr(common, "DATA", data_root / "data")
    monkeypatch.setattr(common, "OUT", data_root / "outputs")
    common.register_identity(STUDENT)
    cwd = tmp_path / "unrelated-working-directory"
    cwd.mkdir()
    env = {**os.environ, "BDP_ROOT": str(data_root), "PYTHONPATH": "",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return SimpleNamespace(checkout=checkout, root=data_root, cwd=cwd, env=env)


def entrypoint(workspace, lab, name, layout):
    source = workspace.checkout / LAB_DIRS[lab] / "附件" / name
    if layout == "attachment":
        return source
    target = workspace.checkout / "submissions" / ("lab" + lab) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def run_script(workspace, script, *args):
    # -S proves identity/import wiring works without optional installed packages.
    return subprocess.run([sys.executable, "-S", str(script), *map(str, args)],
                          cwd=workspace.cwd, env=workspace.env, capture_output=True,
                          text=True, encoding="utf-8", timeout=30)


def recorded_run(workspace, process, lab, exit_code):
    assert process.returncode == exit_code, process.stdout + process.stderr
    envelope = json.loads(process.stdout)
    assert envelope["exit_code"] == exit_code
    record_path = Path(envelope["evidence_json"])
    html_path = Path(envelope["evidence_html"])
    assert record_path.is_relative_to(workspace.root / "outputs" / ("lab" + lab) / "evidence")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    common.verify_evidence(record, lab=lab, student_id=STUDENT)
    assert record["_evidence"] == envelope["_evidence"]
    assert record["exit_code"] == exit_code
    assert record["stdout"] == envelope["stdout"]
    assert record["stderr"] == envelope["stderr"]
    html = html_path.read_text(encoding="utf-8")
    assert html == common.render_evidence(record)
    assert STUDENT in html and "position:sticky" in html
    assert not (workspace.checkout / "outputs").exists()
    return record


@pytest.mark.parametrize("lab,name", ENTRYPOINTS)
@pytest.mark.parametrize("layout", ["attachment", "submission"])
def test_every_entrypoint_rejects_unregistered_identity_before_work(workspace, lab, name, layout):
    (workspace.root / "student.json").unlink()
    process = run_script(workspace, entrypoint(workspace, lab, name, layout))
    assert process.returncode != 0
    assert "缺少学号" in process.stderr
    assert "ModuleNotFoundError" not in process.stderr
    assert not (workspace.root / "outputs").exists()
    assert not (workspace.checkout / "outputs").exists()


@pytest.mark.parametrize("lab,name", ENTRYPOINTS)
def test_import_has_no_execution_or_identity_requirement(workspace, lab, name):
    (workspace.root / "student.json").unlink()
    script = entrypoint(workspace, lab, name, "attachment")
    process = subprocess.run([sys.executable, "-S", "-c",
                              "import runpy,sys; module=runpy.run_path(sys.argv[1]); assert callable(module['main'])",
                              str(script)], cwd=workspace.cwd, env=workspace.env,
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert process.returncode == 0, process.stderr
    assert process.stdout == process.stderr == ""
    assert not (workspace.root / "outputs").exists()


@pytest.mark.parametrize("layout", ["attachment", "submission"])
@pytest.mark.parametrize("failure,code", [("arguments", 2), ("student_todo", 1)])
def test_real_transaction_checker_failure_keeps_exit_code_and_identity(workspace, layout, failure, code):
    checker = entrypoint(workspace, "04", "check_student_transaction.py", layout)
    args = []
    if failure == "student_todo":
        module = entrypoint(workspace, "04", "student_apply_batch.py", layout)
        args = ["--module", module]
    record = recorded_run(workspace, run_script(workspace, checker, *args), "04", code)
    assert record["_evidence"]["stage"] == "check_student_transaction"
    expected_error = "--module" if failure == "arguments" else "NotImplementedError"
    assert expected_error in record["stderr"]
    assert "STUDENT_TRANSACTION_PASS" not in record["stdout"]


@pytest.mark.parametrize("layout", ["attachment", "submission"])
def test_real_atomicity_observation_is_bound_to_isolated_student(workspace, layout):
    script = entrypoint(workspace, "04", "student_atomicity.py", layout)
    record = recorded_run(workspace, run_script(workspace, script), "04", 0)
    target = workspace.root / "outputs/lab04/student-atomicity-early.json"
    result = json.loads(target.read_text(encoding="utf-8"))
    common.verify_evidence(result, lab="04", student_id=STUDENT)
    # The teaching fault remains visible; evidence must not manufacture a pass.
    assert result["commit_early"] is True
    assert result["atomic_contract_passed"] is False
    assert (result["rows_after_failure"], result["offset_after_failure"]) == (1, 0)
    assert (result["final_rows"], result["final_offset"]) == (1, 1)
    assert json.loads(record["stdout"]) == result
    sidecar = json.loads(target.with_name(target.name + ".identity.json").read_text(encoding="utf-8"))
    common.verify_evidence(sidecar, lab="04", student_id=STUDENT)
    assert sidecar["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert sidecar in record["artifacts"]
    assert sidecar["_evidence"]["run_id"] == record["_evidence"]["run_id"]


@pytest.mark.parametrize("layout", ["attachment", "submission"])
def test_quality_policy_reads_and_writes_only_isolated_root(workspace, layout):
    valid = {"event_id": "fixture-1", "event_time": "2026-03-01T00:00:00+00:00",
             "service": "assistant", "model": "small", "input_tokens": 100,
             "output_tokens": 3, "latency_ms": 90, "status": "ok"}
    rows = [valid, valid, {**valid, "event_id": "fixture-policy", "input_tokens": 2500},
            {**valid, "event_id": "fixture-invalid", "input_tokens": -1}]
    source = workspace.root / "data/raw/events.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    script = entrypoint(workspace, "02", "student_quality_policy.py", layout)
    record = recorded_run(workspace, run_script(workspace, script), "02", 0)
    result = json.loads(record["stdout"])
    assert result["raw_rows"] == 4
    assert result["valid_unique"] == result["duplicates"] == 1
    assert result["input_tokens_sum"] == 100
    assert result["rejected_by_reason"] == {"policy_input_limit": 1, "invalid_input_tokens": 1}
    target = workspace.root / f"outputs/lab02/student-policy-{result['max_input_tokens']}.json"
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved == result
    common.verify_evidence(saved, lab="02", student_id=STUDENT)
    assert any(item["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
               for item in record["artifacts"])


@pytest.mark.parametrize("layout", ["attachment", "submission"])
@pytest.mark.parametrize("wrong_gold", [False, True])
def test_inspect_state_uses_isolated_data_and_captures_actual_assertion(workspace, layout, wrong_gold):
    database = workspace.root / "data/state/fixture.sqlite"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as con:
        con.executescript("""CREATE TABLE events(event_id TEXT, event_time TEXT, service TEXT,
            input_tokens INTEGER, output_tokens INTEGER);
            INSERT INTO events VALUES ('increment-1','2026-03-01T00:00:00Z','assistant',10,3);
            CREATE TABLE checkpoint(id INTEGER PRIMARY KEY, offset INTEGER);
            INSERT INTO checkpoint VALUES(1,1);""")
    pointer = database.parent / "latest.json"
    pointer.write_text(json.dumps({"database": "data/state/fixture.sqlite"}), encoding="utf-8")
    gold = workspace.root / "data/gold/realtime_service.json"
    gold.parent.mkdir(parents=True)
    gold.write_text(json.dumps([{"service": "assistant", "requests": 1,
                                 "input_tokens": 999 if wrong_gold else 10,
                                 "output_tokens": 3}]), encoding="utf-8")
    before = database.read_bytes()
    script = entrypoint(workspace, "04", "inspect_state.py", layout)
    record = recorded_run(workspace, run_script(workspace, script), "04", int(wrong_gold))
    assert database.read_bytes() == before
    if wrong_gold:
        assert "AssertionError" in record["stderr"]
    else:
        result = json.loads(record["stdout"])
        assert result["database"] == str(database)
        assert result["matches_gold"] is True and result["rows"] == 1


def test_optional_dependency_failure_is_inside_identity_capture(workspace):
    script = entrypoint(workspace, "02", "inspect_gold.py", "attachment")
    record = recorded_run(workspace, run_script(workspace, script), "02", 1)
    assert "ModuleNotFoundError" in record["stderr"] and "duckdb" in record["stderr"]


def test_object_roundtrip_uses_registered_identity_without_solving_key_task(workspace):
    script = entrypoint(workspace, "01", "student_object_roundtrip.py", "submission")
    code = """import runpy, sys
module = runpy.run_path(sys.argv[1])
assert module['make_key']() == 'shared/raw/demo.json'
try:
    module['main']()
except ModuleNotFoundError:
    pass
assert module['main'].__globals__['STUDENT_ID'] == sys.argv[2]
"""
    process = subprocess.run([sys.executable, "-S", "-c", code, str(script), STUDENT],
                             cwd=workspace.cwd, env=workspace.env, capture_output=True,
                             text=True, encoding="utf-8", timeout=30)
    assert process.returncode == 0, process.stderr
