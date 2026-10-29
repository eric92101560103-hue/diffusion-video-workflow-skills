"""JSON command interface shared by agents and local operators."""

from collections.abc import Sequence
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
import argparse
import json
import sqlite3
import sys
import time

from .workflow import Config, Workflow, WorkflowError
from .instagram import InstagramConnection
from .notifications import SMTPNotifier


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='先審核、後發佈的 Reels 工具')
    root = Path.home() / 'Desktop' / 'Reels 成片'
    parser.add_argument('--source', type=Path, default=root / '待發佈')
    parser.add_argument('--published', type=Path, default=root / '已發佈')
    parser.add_argument(
        '--database', type=Path,
        default=Path.home() / 'Library' / 'Application Support' / 'ReelPublisher' / 'state.sqlite3',
    )
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('scan', help='單次掃描，不上傳、不發佈')
    commands.add_parser('list', help='查看候選與審核狀態')
    get = commands.add_parser('get')
    get.add_argument('id')
    replay = commands.add_parser('replay', help='明確建立重發候選，仍需審核')
    replay.add_argument('path', type=Path)
    replay.add_argument('--confirm-replay', action='store_true', required=True)
    caption = commands.add_parser('caption', help='修改文案；修改會使舊核准失效')
    caption.add_argument('id')
    text = caption.add_mutually_exclusive_group(required=True)
    text.add_argument('--text')
    text.add_argument('--file', type=Path)
    preview = commands.add_parser('preview', help='按給定順序建議日期，不啟用發佈')
    preview.add_argument('ids', nargs='+')
    preview.add_argument('--first-date', type=date.fromisoformat)
    approve = commands.add_parser('approve', help='確認已審核版本，不上傳或啟用雲端')
    approve.add_argument('--versions-file', type=Path, required=True,
                         help='JSON object: candidate ID to reviewed revision number')
    tick = commands.add_parser('tick', help='到期才掃描並寄信；需先配置 SMTP')
    tick.add_argument('--first-scan', type=datetime.fromisoformat, required=True)
    watch = commands.add_parser('watch', help='持續檢查到期掃描；需由本機背景服務維持執行')
    watch.add_argument('--first-scan', type=datetime.fromisoformat, required=True)
    commands.add_parser('notices', help='查看通知結果，unknown 不自動重寄')
    commands.add_parser('instagram-check', help='只讀核對授權帳號，不代表已取得發佈權限')
    arguments = parser.parse_args(argv)
    try:
        config = Config(arguments.database, arguments.source, arguments.published)
        with Workflow(config) as workflow:
            if arguments.command == 'scan':
                output: object = asdict(workflow.scan())
            elif arguments.command == 'list':
                output = [asdict(candidate) for candidate in workflow.list_candidates()]
            elif arguments.command == 'get':
                output = asdict(workflow.get(arguments.id))
            elif arguments.command == 'replay':
                output = asdict(workflow.replay(arguments.path, confirmed=arguments.confirm_replay))
            elif arguments.command == 'caption':
                caption_text = arguments.file.read_text() if arguments.file else arguments.text
                output = asdict(workflow.set_caption(arguments.id, caption_text))
            elif arguments.command == 'preview':
                output = [asdict(item) for item in workflow.preview(arguments.ids, first_date=arguments.first_date)]
            elif arguments.command == 'approve':
                versions = json.loads(arguments.versions_file.read_text())
                if not isinstance(versions, dict) or not all(
                    isinstance(key, str) and type(value) is int for key, value in versions.items()
                ):
                    raise WorkflowError('核准檔必須是候選 ID 與版本整數的 JSON 對照')
                output = [asdict(item) for item in workflow.approve(versions)]
            elif arguments.command == 'tick':
                output = asdict(workflow.tick(first_scan=arguments.first_scan, notifier=SMTPNotifier.from_environment()))
            elif arguments.command == 'watch':
                notifier = SMTPNotifier.from_environment()
                try:
                    while True:
                        result = workflow.tick(first_scan=arguments.first_scan, notifier=notifier)
                        if result.scanned:
                            print(json.dumps(asdict(result), ensure_ascii=False), flush=True)
                        time.sleep(60)
                except KeyboardInterrupt:
                    return 130
            elif arguments.command == 'notices':
                output = [asdict(notice) for notice in workflow.notification_status()]
            else:
                output = {'account': asdict(workflow.check_instagram(InstagramConnection.from_environment())),
                          'publishing_permission': 'not_verified', 'published': False}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (WorkflowError, OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
