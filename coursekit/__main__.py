import argparse
import json
import sys
import traceback

from .common import (IdentityError, emit, normalize_lab, register_identity,
                     require_identity, save_run)


def main():
    parser = argparse.ArgumentParser(description='BDP：模拟服务使用分析与规则查询平台')
    sub = parser.add_subparsers(dest='command', required=True)
    identity = sub.add_parser('identity')
    identity.add_argument('--student-id', required=True)
    identity.add_argument('--lab', default='01')
    identity.add_argument('--stage', default='start')
    seed = sub.add_parser('seed')
    seed.add_argument('--rows', type=int, default=20000)
    l1 = sub.add_parser('lab01')
    l1.add_argument('--endpoint')
    sub.add_parser('lab02')
    l3 = sub.add_parser('lab03')
    l3.add_argument('--workers', type=int, default=2)
    l3.add_argument('--partitions', type=int, default=8)
    sub.add_parser('lab04')
    l5 = sub.add_parser('lab05')
    l5.add_argument('--mode', choices=['lexical', 'semantic'], default='lexical')
    l6 = sub.add_parser('lab06')
    l6.add_argument('--split', choices=['dev', 'test'], default='dev')
    l6.add_argument('--generator', choices=['extractive', 'ollama'], default='extractive')
    freeze = sub.add_parser('freeze')
    freeze.add_argument('--generator', choices=['extractive', 'ollama'], default='extractive')
    l7 = sub.add_parser('lab07')
    l7.add_argument('--requests', type=int, default=20)
    sub.add_parser('lab08')
    capture = sub.add_parser('capture', help='Capture a finite command with native student evidence')
    capture.add_argument('--lab', required=True)
    capture.add_argument('--stage', default='independent')
    capture.add_argument('arguments', nargs=argparse.REMAINDER)
    manifest = sub.add_parser('submission-manifest')
    manifest.add_argument('--lab', required=True)
    manifest.add_argument('--directory', required=True)
    manifest.add_argument('--report', required=True)
    check = sub.add_parser('submission-check', help='Student precheck; valid submissions remain pending teacher review')
    check.add_argument('--directory', required=True)
    check.add_argument('--student-id', required=True, help='Expected student ID for the precheck')
    args = parser.parse_args()
    try:
        if args.command == 'identity':
            register_identity(args.student_id, args.lab)
            emit(args.lab, args.stage, {'identity_note': '本人学号仅用于证据关联；每张评分截图必须带学号，不能替代原创性验收。'})
        elif args.command == 'submission-check':
            from .evidence import check_submission
            result = check_submission(args.directory, args.student_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2  # A successful student precheck never constitutes teacher approval.
        else:
            require_identity()
            if args.command in ['seed', 'lab01', 'lab02', 'lab03', 'lab04']:
                from . import pipeline
                kwargs = vars(args).copy()
                name = kwargs.pop('command')
                getattr(pipeline, name)(**kwargs)
            elif args.command in ['lab05', 'lab06']:
                from . import intelligence
                kwargs = vars(args).copy()
                name = kwargs.pop('command')
                getattr(intelligence, name)(**kwargs)
            elif args.command == 'freeze':
                from .intelligence import freeze_settings
                emit('06', 'freeze', freeze_settings(generator=args.generator))
            elif args.command == 'lab07':
                from .service import lab07
                lab07(requests=args.requests)
            elif args.command == 'lab08':
                from .governance import lab08
                lab08()
            elif args.command == 'capture':
                from .evidence import capture_command
                return capture_command(args.lab, args.stage, args.arguments)
            elif args.command == 'submission-manifest':
                from .evidence import build_submission
                emit(args.lab, 'submission', build_submission(args.directory, args.lab, args.report))
    except Exception as exc:
        message = {'passed': False, 'error': f'{type(exc).__name__}: {exc}'}
        if args.command != 'submission-check':
            try:
                require_identity()
                lab = getattr(args, 'lab', None) or ('06' if args.command == 'freeze' else
                      args.command[3:] if args.command.startswith('lab') else '00')
                record, raw, page = save_run(normalize_lab(lab), 'failed-' + args.command,
                                            message, stderr=traceback.format_exc(), exit_code=1)
                message.update(_evidence=record['_evidence'], evidence_json=str(raw), evidence_html=str(page))
            except (IdentityError, ValueError):
                pass
        print(json.dumps(message, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
