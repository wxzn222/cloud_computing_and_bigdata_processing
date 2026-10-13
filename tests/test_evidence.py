"""Student evidence contracts using isolated roots and real short subprocesses.

The PNG fixture is a valid, tiny raster image, deliberately without readable text.
These tests exercise student evidence, identity and integrity prechecks only.
Successful prechecks remain pending until screenshots and report identity are reviewed.
"""
import hashlib
import json
import re
import shutil
import struct
import sys
import uuid
import zlib
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest

from coursekit import common, evidence


STUDENT = "20260042"  # Synthetic student IDs, not actual student data.
OTHER_STUDENT = "20260099"
LAB = "01"


def dump_json(path, value):
    """Write fixture/tamper input without adding implementation-generated metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_bytes(rgb=(30, 90, 160)):
    """Build an actual 2x2 RGB PNG with compressed scanlines and correct CRCs."""
    def chunk(kind, content):
        return (struct.pack(">I", len(content)) + kind + content
                + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF))

    row = b"\x00" + bytes(rgb) * 2
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * 2)) + chunk(b"IEND", b""))


class EvidenceHTML(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.sections = {tag: [] for tag in ("header", "style", "pre")}
        self.active = None
        self.scripts = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag in self.sections:
            self.active = tag
        if tag == "script":
            self.scripts.append(attrs)

    def handle_endtag(self, tag):
        if self.active == tag:
            self.active = None

    def handle_data(self, data):
        if self.active:
            self.sections[self.active].append(data)

    def text(self, tag):
        return "".join(self.sections[tag])


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = (tmp_path / "course").resolve()
    root.mkdir()
    monkeypatch.setenv("BDP_ROOT", str(root))
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "DATA", root / "data")
    monkeypatch.setattr(common, "OUT", root / "outputs")
    monkeypatch.setattr(common, "_WRITTEN", {})
    monkeypatch.setattr(common, "_RUN_ID", uuid.uuid4().hex)
    monkeypatch.setattr(common, "_STARTED_AT", datetime.now(timezone.utc).isoformat())
    return root


@pytest.fixture
def registered(workspace):
    common.register_identity(STUDENT, LAB)
    return workspace


@pytest.fixture
def make_submission(registered, tmp_path):
    """Produce native run JSON/HTML; use synthetic business output, not lab baselines."""
    def make(*, lab=LAB, greeting=False, screenshots=1, report_id=STUDENT):
        root = (tmp_path / ("submission-" + uuid.uuid4().hex)).resolve()
        (root / "evidence").mkdir(parents=True)
        report = root / "report.md"
        report.write_text(f"# 实验报告\n学号：{report_id}\n结果：1 + 1 = 2。\n", encoding="utf-8")
        payload = {"identity_note": "身份问候不是实验结果"} if greeting else {"sum": sum([1, 1])}
        record, source_json, source_html = common.save_run(lab, "complete", payload)
        run_json = root / "evidence" / "run.json"
        run_html = run_json.with_suffix(".html")
        shutil.copyfile(source_json, run_json)
        shutil.copyfile(source_html, run_html)
        shots = []
        for index in range(screenshots):
            shot = root / "evidence" / f"screen-{index}.png"
            shot.write_bytes(png_bytes((30 + index, 90, 160)))
            shots.append(shot)
        return SimpleNamespace(root=root, report=report, run_json=run_json,
                               run_html=run_html, screenshots=shots, record=record)
    return make


def build(package):
    return evidence.build_submission(package.root, LAB, package.report.name)


@pytest.fixture
def submission(make_submission):
    package = make_submission()
    build(package)
    return package


@pytest.mark.parametrize("operation", ["require", "write", "emit", "capture"])
def test_unregistered_run_fails_before_creating_evidence(workspace, operation):
    marker = workspace / "child-was-started"
    operations = {
        "require": common.require_identity,
        "write": lambda: common.write_json(common.OUT / "lab01" / "result.json", {"sum": 2}),
        "emit": lambda: common.emit(LAB, "complete", {"sum": 2}),
        "capture": lambda: evidence.capture_command(
            LAB, "capture", [sys.executable, "-c",
                             "from pathlib import Path; Path(__import__('sys').argv[1]).touch()", str(marker)]),
    }
    with pytest.raises(common.IdentityError, match="缺少学号"):
        operations[operation]()
    assert not marker.exists()
    assert not common.OUT.exists()


@pytest.mark.parametrize("student", ["", " ", "UNREGISTERED", "unregistered", "STUDENT_ID",
                                     "YOUR_STUDENT_ID", "wrong id", "../20260042", "x" * 65, None])
def test_identity_rejects_invalid_or_placeholder_id(workspace, student):
    with pytest.raises(common.IdentityError):
        common.register_identity(student, LAB)
    assert not (workspace / "student.json").exists()


def test_existing_unregistered_identity_is_rejected(workspace):
    dump_json(workspace / "student.json", {"student_id": "UNREGISTERED"})
    with pytest.raises(common.IdentityError):
        common.require_identity()


def test_registered_identity_cannot_relabel_existing_results(registered):
    result = common.OUT / "lab01" / "result.json"
    common.write_json(result, {"sum": 2})
    previous_identity = (registered / "student.json").read_bytes()
    previous_result = result.read_bytes()
    assert common.register_identity(STUDENT, LAB) == STUDENT
    with pytest.raises(common.IdentityError, match="改署名|不同学号"):
        common.register_identity(OTHER_STUDENT, LAB)
    assert (registered / "student.json").read_bytes() == previous_identity
    assert result.read_bytes() == previous_result


@pytest.mark.parametrize("changed_identity", [OTHER_STUDENT, "UNREGISTERED"])
def test_old_evidence_rejected_after_identity_file_is_changed(registered, changed_identity):
    result = common.OUT / "lab01" / "result.json"
    common.write_json(result, {"sum": 2})
    dump_json(registered / "student.json", {"student_id": changed_identity})
    with pytest.raises(common.IdentityError):
        common.read_evidence(result, LAB)


def test_write_json_dict_binds_metadata_without_mutating_input(registered):
    path = common.OUT / "lab01" / "metrics.json"
    source = {"count": 2, "message": "中文结果"}
    common.write_json(path, source)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert source == {"count": 2, "message": "中文结果"}
    assert {key: value for key, value in saved.items() if key != "_evidence"} == source
    meta = common.verify_evidence(saved, LAB, STUDENT)
    assert meta["student_id"] == STUDENT
    assert meta["experiment_id"] == LAB
    assert meta["stage"] == "metrics"
    assert re.fullmatch(r"[0-9a-f]{32}", meta["run_id"])
    assert datetime.fromisoformat(meta["captured_at"]).tzinfo is not None
    with pytest.raises(common.IdentityError, match="学号"):
        common.verify_evidence(saved, LAB, OTHER_STUDENT)
    with pytest.raises(common.IdentityError, match="编号"):
        common.verify_evidence(saved, "02", STUDENT)


def test_write_json_list_keeps_schema_and_hash_bound_sidecar(registered):
    path = common.OUT / "lab01" / "rows.json"
    rows = [{"name": "甲", "count": 1}, {"name": "乙", "count": 2}]
    common.write_json(path, rows)
    assert json.loads(path.read_text(encoding="utf-8")) == rows
    sidecar = json.loads(path.with_name(path.name + ".identity.json").read_text(encoding="utf-8"))
    assert sidecar["file"] == "outputs/lab01/rows.json"
    assert sidecar["sha256"] == digest(path)
    assert common.verify_evidence(sidecar, LAB, STUDENT)["stage"] == "rows"
    _, run_path, _ = common.save_run(LAB, "complete", {"count": 2})
    record = json.loads(run_path.read_text(encoding="utf-8"))
    assert sidecar in record["artifacts"]


def test_emit_creates_native_json_and_persistent_identity_header(registered, capsys):
    payload = {"message": "中文结果 <script>alert('x')</script>", "count": 2}
    assert common.emit(LAB, "complete", payload) == payload
    printed = json.loads(capsys.readouterr().out)
    record = json.loads(Path(printed["evidence_json"]).read_text(encoding="utf-8"))
    view = EvidenceHTML(Path(printed["evidence_html"]).read_text(encoding="utf-8"))
    assert record["kind"] == "coursekit.run"
    assert record["result"] == payload
    assert printed["STUDENT_ID"] == STUDENT
    assert printed["EXPERIMENT_ID"] == LAB
    assert printed["RUN_ID"] == record["_evidence"]["run_id"]
    assert STUDENT in view.text("header")
    assert "实验/项目 " + LAB in view.text("header")
    assert printed["RUN_ID"] in view.text("header")
    header_css = re.search(r"header\s*\{([^}]+)\}", view.text("style"))
    assert header_css is not None
    assert re.search(r"position\s*:\s*(sticky|fixed)", header_css[1])
    assert re.search(r"top\s*:\s*0(?:[;\s]|$)", header_css[1])
    assert json.loads(view.text("pre")) == record
    assert not view.scripts


@pytest.mark.parametrize("exit_code", [0, 7])
def test_capture_real_child_chinese_output_exit_and_identity(registered, capsys, exit_code):
    code = ("import os,sys; from pathlib import Path; "
            "p=Path(os.environ['BDP_ROOT'])/'outputs'/'lab01'/'child.txt'; "
            "p.parent.mkdir(parents=True,exist_ok=True); p.write_text('子进程制品',encoding='utf-8'); "
            "print('真实子进程中文输出'); print('中文诊断',file=sys.stderr); "
            f"sys.exit({exit_code})")
    command = [sys.executable, "-c", code]
    assert evidence.capture_command(LAB, "child", ["--", *command]) == exit_code
    printed = json.loads(capsys.readouterr().out)
    assert printed["exit_code"] == exit_code
    assert printed["stdout"] == "真实子进程中文输出\n"
    assert printed["stderr"] == "中文诊断\n"
    record = common.read_json(printed["evidence_json"])
    assert record["command"] == command
    assert record["exit_code"] == exit_code
    assert record["stdout"] == printed["stdout"]
    assert record["stderr"] == printed["stderr"]
    meta = common.verify_evidence(record, LAB, STUDENT)
    assert meta == printed["_evidence"]
    artifact = record["artifacts"][0]
    child_file = registered / artifact["file"]
    assert child_file.read_text(encoding="utf-8") == "子进程制品"
    assert artifact["sha256"] == digest(child_file)
    assert artifact["_evidence"] == meta
    sidecar = common.read_json(child_file.with_name(child_file.name + ".identity.json"))
    assert sidecar == artifact
    view = EvidenceHTML(Path(printed["evidence_html"]).read_text(encoding="utf-8"))
    assert STUDENT in view.text("header") and meta["run_id"] in view.text("header")
    assert "真实子进程中文输出" in view.text("pre")


@pytest.mark.parametrize("case", ["missing_identity", "foreign_result", "other_lab",
                                  "identity_greeting", "no_native_run", "no_screenshot", "no_html"])
def test_submission_requires_current_student_actual_lab_run_and_screenshot(make_submission, registered, case):
    package = make_submission(lab="02" if case == "other_lab" else LAB,
                              greeting=case == "identity_greeting",
                              screenshots=0 if case == "no_screenshot" else 1)
    if case == "missing_identity":
        (registered / "student.json").unlink()
    elif case == "no_html":
        package.run_html.unlink()
    elif case in {"foreign_result", "no_native_run"}:
        record = common.read_json(package.run_json)
        if case == "foreign_result":
            record["_evidence"]["student_id"] = OTHER_STUDENT
            package.run_html.write_text(common.render_evidence(record), encoding="utf-8")
        else:
            record.pop("kind")
            package.run_html.unlink()
        dump_json(package.run_json, record)
    with pytest.raises(ValueError):
        build(package)
    assert not (package.root / "submission-manifest.json").exists()


@pytest.mark.parametrize("report_text", ["# 报告\n未写学号。", f"# 报告\n学号：{OTHER_STUDENT}。"])
def test_submission_rejects_report_without_current_student_id(make_submission, report_text):
    package = make_submission()
    package.report.write_text(report_text, encoding="utf-8")
    with pytest.raises(common.IdentityError, match="报告.*学号"):
        build(package)


def test_submission_rejects_non_image_bytes_with_png_extension(make_submission):
    package = make_submission()
    package.screenshots[0].write_text("not an image", encoding="utf-8")
    with pytest.raises(ValueError, match="PNG/JPEG"):
        build(package)


def test_submission_rejects_tampered_native_html_before_manifest(make_submission):
    package = make_submission()
    original = package.run_html.read_text(encoding="utf-8")
    package.run_html.write_text(original.replace(STUDENT, OTHER_STUDENT), encoding="utf-8")
    with pytest.raises(ValueError, match="HTML.*原始记录"):
        build(package)


def test_submission_without_teacher_review_is_pending_not_passed(submission):
    result = evidence.check_submission(submission.root, STUDENT)
    assert result["passed"] is False
    assert result["status"] == "pending_teacher_screenshot_review"
    assert result["student_id"] == STUDENT
    assert result["experiment_id"] == LAB


def test_submission_rejects_wrong_acceptance_student(submission):
    with pytest.raises(common.IdentityError, match="学号"):
        evidence.check_submission(submission.root, OTHER_STUDENT)


@pytest.mark.parametrize("changed_file", ["report", "screenshot", "run"])
def test_student_precheck_detects_tampering_and_stays_pending_after_rebuild(submission, changed_file):
    if changed_file == "report":
        submission.report.write_text(f"# 更正后的报告\n学号：{STUDENT}\n补充解释。", encoding="utf-8")
    elif changed_file == "screenshot":
        submission.screenshots[0].write_bytes(png_bytes((160, 40, 20)))
    else:
        record = common.read_json(submission.run_json)
        record["result"] = {"sum": 4}
        dump_json(submission.run_json, record)
        submission.run_html.write_text(common.render_evidence(record), encoding="utf-8")
    with pytest.raises(ValueError, match="哈希变化"):
        evidence.check_submission(submission.root, STUDENT)
    build(submission)
    result = evidence.check_submission(submission.root, STUDENT)
    assert result["passed"] is False
    assert result["status"] == "pending_teacher_screenshot_review"


def test_submission_cli_pending_and_invalid(submission, monkeypatch, capsys):
    from coursekit.__main__ import main
    argv = ["coursekit", "submission-check", "--directory", str(submission.root),
            "--student-id", STUDENT]
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == 2
    assert json.loads(capsys.readouterr().out)["passed"] is False
    submission.report.write_text("tampered", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == 1
    assert json.loads(capsys.readouterr().err)["passed"] is False


def test_capture_callable_failure_preserves_traceback_and_identity_html(registered, capsys):
    def callback_root_cause():
        raise LookupError("回调原始中文故障")

    def failing_callback():
        print("回调失败前的中文输出")
        print("回调失败前的诊断", file=sys.stderr)
        callback_root_cause()

    assert evidence.capture_callable(LAB, "callback-failure", failing_callback) == 1
    printed = json.loads(capsys.readouterr().out)
    record = common.read_json(printed["evidence_json"])
    assert printed["exit_code"] == record["exit_code"] == 1
    assert printed["stdout"] == record["stdout"] == "回调失败前的中文输出\n"
    assert printed["stderr"] == record["stderr"]
    for original_detail in (
        "回调失败前的诊断", "Traceback (most recent call last)",
        Path(__file__).name, "in failing_callback", "in callback_root_cause",
        "LookupError: 回调原始中文故障",
    ):
        assert original_detail in record["stderr"]
    meta = common.verify_evidence(record, LAB, STUDENT)
    assert printed["_evidence"] == meta
    view = EvidenceHTML(Path(printed["evidence_html"]).read_text(encoding="utf-8"))
    assert STUDENT in view.text("header")
    assert "实验/项目 " + LAB in view.text("header")
    assert meta["run_id"] in view.text("header")
    assert json.loads(view.text("pre")) == record


def test_capture_callable_raw_json_gets_identity_sidecar_and_returns_zero(registered, capsys):
    artifact_path = common.OUT / "lab01" / "callback-original.json"
    original = {"items": [{"message": "回调原始结果"}], "count": 1}
    raw_bytes = json.dumps(original, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def successful_callback():
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(raw_bytes)  # Intentionally bypass common.write_json.
        print("回调完成")

    assert evidence.capture_callable(LAB, "callback-success", successful_callback) == 0
    printed = json.loads(capsys.readouterr().out)
    record = common.read_json(printed["evidence_json"])
    assert printed["exit_code"] == record["exit_code"] == 0
    assert printed["stdout"] == record["stdout"] == "回调完成\n"
    assert printed["stderr"] == record["stderr"] == ""
    assert artifact_path.read_bytes() == raw_bytes
    assert common.read_json(artifact_path) == original
    assert "_evidence" not in common.read_json(artifact_path)
    sidecar = common.read_json(artifact_path.with_name(artifact_path.name + ".identity.json"))
    assert sidecar["file"] == "outputs/lab01/callback-original.json"
    assert sidecar["sha256"] == digest(artifact_path)
    assert record["artifacts"] == [sidecar]
    assert common.verify_evidence(sidecar, LAB, STUDENT) == record["_evidence"]
    assert printed["_evidence"] == record["_evidence"]
    assert Path(printed["evidence_html"]).is_file()
