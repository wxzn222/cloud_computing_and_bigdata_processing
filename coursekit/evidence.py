"""Capture finite commands and precheck student submissions; never approve them."""
from __future__ import annotations

import json
import contextlib
import io
import os
import subprocess
import traceback
from pathlib import Path

from . import common


def _bind_changed_outputs(directory, before, lab, stage):
    artifacts = []
    for path in sorted(directory.rglob('*')):
        if (not path.is_file() or 'evidence' in path.relative_to(directory).parts
                or path.name.endswith('.identity.json') or path.suffix == '.tmp'):
            continue
        digest = common.sha256(path)
        if before.get(path.resolve()) != digest:
            item = {'file': path.resolve().relative_to(common.ROOT).as_posix(),
                    'sha256': digest, '_evidence': common.evidence_metadata(lab, stage)}
            common._write_plain_json(path.with_name(path.name + '.identity.json'), item)
            artifacts.append(item)
    return artifacts


def capture_callable(lab, stage, operation):
    """Native entrypoint for shipped student scripts, including their real failures."""
    common.require_identity()
    lab = common.normalize_lab(lab)
    directory = common.OUT / ('lab' + lab)
    before = {p.resolve(): common.sha256(p) for p in directory.rglob('*') if p.is_file()}
    stdout, stderr, code = io.StringIO(), io.StringIO(), 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            operation()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            if isinstance(exc.code, str):
                print(exc.code, file=stderr)
        except Exception:
            code = 1
            traceback.print_exc(file=stderr)
    record, raw, page = common.save_run(
        lab, stage, exit_code=code, stdout=stdout.getvalue(), stderr=stderr.getvalue(),
        artifacts=_bind_changed_outputs(directory, before, lab, stage))
    print(json.dumps({'_evidence': record['_evidence'], 'exit_code': code,
                      'stdout': record['stdout'], 'stderr': record['stderr'],
                      'evidence_json': str(raw), 'evidence_html': str(page)}, ensure_ascii=False, indent=2))
    return code


def capture_command(lab, stage, command):
    common.require_identity()
    lab = common.normalize_lab(lab)
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        raise ValueError('capture需要 -- 后的实际命令；不要用于常驻HTTP服务。')
    directory = common.OUT / ('lab' + lab)
    before = {p.resolve(): common.sha256(p) for p in directory.rglob('*') if p.is_file()}
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    try:
        process = subprocess.run(command, env=env, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace')
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except OSError as exc:
        code, stdout, stderr = 127, '', f'{type(exc).__name__}: {exc}'
    artifacts = _bind_changed_outputs(directory, before, lab, stage)
    record, json_path, html_path = common.save_run(
        lab, stage, command=list(command), exit_code=code, stdout=stdout,
        stderr=stderr, artifacts=artifacts)
    print(json.dumps({'_evidence': record['_evidence'], 'exit_code': code,
                      'stdout': stdout, 'stderr': stderr,
                      'evidence_json': str(json_path), 'evidence_html': str(html_path)},
                     ensure_ascii=False, indent=2))
    return code


def _inside(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('提交路径须为包内使用/分隔的相对路径。')
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts:
        raise ValueError('提交文件不得指向包外。')
    path = root / part
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError('提交不接受符号链接。')
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'缺少提交文件：{relative}')
    return path


def _files(root):
    blocked = {'.venv', 'models', 'wheelhouse', '.git', '__pycache__'}
    rows = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in blocked for part in relative.parts):
            raise ValueError('提交包含环境、模型、缓存或Git目录，请按评分清单精简。')
        if path.is_symlink():
            raise ValueError('提交不接受符号链接。')
        if path.is_file() and relative.as_posix() != 'submission-manifest.json' and path.name != '.DS_Store':
            rows.append({'file': relative.as_posix(), 'sha256': common.sha256(path)})
    return rows


def _image(path):
    with path.open('rb') as stream:
        header = stream.read(12)
    if not (header.startswith(b'\x89PNG\r\n\x1a\n') or header.startswith(b'\xff\xd8\xff')):
        raise ValueError(f'截图不是PNG/JPEG：{path.name}')


def _validate_content(root, files, report, student, lab):
    report_path = _inside(root, report)
    if report_path.suffix.lower() not in {'.md', '.pdf'}:
        raise ValueError('报告须为Markdown或PDF。')
    if report_path.suffix.lower() == '.md' and student not in report_path.read_text(encoding='utf-8-sig'):
        raise common.IdentityError('报告正文缺少本人学号。')
    runs, screenshots = [], []
    for item in files:
        path = _inside(root, item['file'])
        relative = Path(item['file'])
        if relative.parts[0] != 'evidence':
            continue
        if path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
            _image(path)
            screenshots.append(item)
        elif path.suffix.lower() == '.json':
            value = common.read_json(path)
            if isinstance(value, dict) and '_evidence' in value:
                meta = common.verify_evidence(value, student_id=student)
            else:
                sidecar = path.with_name(path.name + '.identity.json')
                if not sidecar.is_file():
                    raise common.IdentityError(f'{item["file"]}缺少学号元数据或原生身份旁证。')
                side = common.read_json(sidecar)
                meta = common.verify_evidence(side, student_id=student)
                if side.get('sha256') != item['sha256']:
                    raise ValueError('原始结果与身份旁证哈希不一致。')
            if isinstance(value, dict) and value.get('kind') == 'coursekit.run':
                # A separate identity greeting is not an experiment result.
                payload = value.get('result')
                greeting = isinstance(payload, dict) and 'identity_note' in payload
                if not greeting:
                    if not path.with_suffix('.html').is_file():
                        raise ValueError('真实运行JSON缺少同名原生证据HTML。')
                    runs.append({**item, '_evidence': meta})
        elif path.suffix.lower() == '.html':
            paired = path.with_suffix('.json')
            if not paired.is_file():
                raise ValueError('证据HTML缺少同名原始运行JSON。')
            record = common.read_json(paired)
            common.verify_evidence(record, student_id=student)
            if record.get('kind') != 'coursekit.run' or path.read_text(encoding='utf-8') != common.render_evidence(record):
                raise ValueError('证据HTML与原始记录不符，不能改学号或拼接结果。')
    if not any(row['_evidence']['experiment_id'] == lab for row in runs):
        raise ValueError('缺少本实验/项目的真实运行JSON，单独身份输出不能代替结果。')
    if not screenshots:
        raise ValueError('缺少带学号的PNG/JPEG实际截图。')
    return runs, screenshots


def build_submission(directory, lab, report):
    root = Path(directory).resolve()
    if not root.is_dir():
        raise ValueError('提交目录不存在。')
    student, lab = common.require_identity(), common.normalize_lab(lab)
    files = _files(root)
    runs, screenshots = _validate_content(root, files, report, student, lab)
    manifest = {'kind': 'coursekit.submission', '_evidence': common.evidence_metadata(lab, 'submission'),
                'report': {'file': report, 'sha256': common.sha256(_inside(root, report))},
                'files': files, 'runs': runs, 'screenshots': screenshots,
                'status': 'pending_teacher_screenshot_review',
                'note': '提交清单仅用于材料预检查，须经授课老师逐张复核后方可验收。'}
    target = root / 'submission-manifest.json'
    common._write_plain_json(target, manifest)
    return {'manifest': str(target), 'sha256': common.sha256(target),
            'student_id': student, 'experiment_id': lab, 'status': manifest['status']}


def check_submission(directory, student_id):
    """Check identity and integrity only. Success still requires teacher review."""
    root = Path(directory).resolve()
    student = common.validate_student_id(student_id)
    target = _inside(root, 'submission-manifest.json')
    manifest = common.read_json(target)
    meta = common.verify_evidence(manifest, student_id=student)
    if manifest.get('kind') != 'coursekit.submission':
        raise ValueError('不是课程提交清单。')
    actual_files = _files(root)
    if actual_files != manifest.get('files'):
        raise ValueError('提交文件缺失、增加或哈希变化；修改后须重建清单和重新复核。')
    report = manifest['report']
    if common.sha256(_inside(root, report['file'])) != report['sha256']:
        raise ValueError('报告哈希不符。')
    runs, screenshots = _validate_content(root, actual_files, report['file'], student, meta['experiment_id'])
    if runs != manifest.get('runs') or screenshots != manifest.get('screenshots'):
        raise ValueError('运行记录或截图清单不符。')
    result = {'student_id': student, 'experiment_id': meta['experiment_id'],
              'manifest_sha256': common.sha256(target), 'passed': False,
              'status': 'pending_teacher_screenshot_review',
              'scope': '学生预检查仅核对证据结构、声明身份和完整性；截图、报告身份及真实结果须教师人工复核。'}
    return result
