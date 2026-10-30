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


def main(argv: Sequence[str] | None = None, *, local_only: bool = False) -> int:
    parser = argparse.ArgumentParser(description='先審核、後發佈的 Reels 工具')
    root = Path.home() / 'Desktop' / 'Reels 成片'
    parser.add_argument('--source', type=Path, default=root / '待發佈')
    parser.add_argument('--published', type=Path, default=root / '已發佈')
    parser.add_argument(
        '--database', type=Path,
        default=Path.home() / 'Library' / 'Application Support' / 'ReelPublisher' / 'state.sqlite3',
    )
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('preflight', help='只讀檢查本機依賴與設定，不建立狀態')
    chat_setup = commands.add_parser('chat-setup', help='配置 Codex 對話掃描，預設停用')
    chat_setup.add_argument('--first-scan', type=datetime.fromisoformat, required=True)
    chat_enable = commands.add_parser('chat-enable', help='確認主要掃描通道；不建立定時任務')
    chat_enable.add_argument('--confirm-primary', action='store_true', required=True)
    release = commands.add_parser('scan-release-primary', help='確認舊掃描器已停後釋放主通道；不清歷史')
    release.add_argument('--confirm-stopped', action='store_true', required=True)
    commands.add_parser('chat-disable', help='停用本機對話檢查，保留候選及回報紀錄')
    commands.add_parser('chat-status', help='查看本機模式及未確認回報，不領取新通知')
    commands.add_parser('chat-check', help='到期掃描並領取一次待確認回報，不代表已送達')
    report = commands.add_parser('chat-report', help='人工核對指定回報，不自動重報')
    report.add_argument('id')
    chat_resolve = commands.add_parser('chat-resolve', help='明確核對 received 或 not-delivered')
    chat_resolve.add_argument('id')
    chat_resolve.add_argument('--outcome', choices=['received', 'not-delivered'], required=True)
    chat_resolve.add_argument('--confirm-checked', action='store_true', required=True)
    chat_import = commands.add_parser('chat-import', help='明確匯入舊 JSON 通知紀錄，視為未確認')
    chat_import.add_argument('--ledger', type=Path, required=True)
    chat_import.add_argument('--confirm-checked', action='store_true', required=True)
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
    if not local_only:
        tick = commands.add_parser('tick', help='到期才掃描並寄信；需先配置 SMTP')
        tick.add_argument('--first-scan', type=datetime.fromisoformat, required=True)
        watch = commands.add_parser('watch', help='持續檢查到期掃描；需由本機背景服務維持執行')
        watch.add_argument('--first-scan', type=datetime.fromisoformat, required=True)
        commands.add_parser('scan-status', help='查看最後掃描結果與下一次到期時間')
        resolve = commands.add_parser('notice-resolve', help='人工核對 unknown 後才允許標記或重寄')
        resolve.add_argument('id')
        resolve.add_argument('--outcome', choices=['delivered', 'not-delivered'], required=True)
        resolve.add_argument('--confirm-checked', action='store_true', required=True)
        commands.add_parser('notices', help='查看通知結果，unknown 不自動重寄')
        commands.add_parser('instagram-check', help='只讀核對授權帳號，不代表已取得發佈權限')
        service = commands.add_parser('scan-service-prepare', help='只產生未啟用的本機背景掃描設定')
        service.add_argument('--directory', type=Path, required=True)
        service.add_argument('--first-scan', type=datetime.fromisoformat, required=True)
    arguments = parser.parse_args(argv)
    try:
        config = Config(arguments.database, arguments.source, arguments.published)
        if arguments.command == 'preflight':
            from .local_plugin import preflight
            checked = preflight(config)
            print(json.dumps(checked, ensure_ascii=False))
            return 0 if checked['runtime_ready'] else 1
        if arguments.command == 'scan-service-prepare':
            from .scan_service import prepare
            print(json.dumps(prepare(config, arguments.directory, arguments.first_scan), ensure_ascii=False))
            return 0
        output: object
        with Workflow(config) as workflow:
            if arguments.command == 'chat-setup':
                output = workflow.chat_setup(first_scan=arguments.first_scan)
            elif arguments.command == 'chat-enable':
                output = workflow.chat_enable(confirmed=arguments.confirm_primary)
            elif arguments.command == 'scan-release-primary':
                output = workflow.scan_release_primary(confirmed=arguments.confirm_stopped)
            elif arguments.command == 'chat-disable':
                output = workflow.chat_disable()
            elif arguments.command == 'chat-status':
                output = workflow.chat_status()
            elif arguments.command == 'chat-check':
                output = asdict(workflow.chat_check())
            elif arguments.command == 'chat-report':
                output = asdict(workflow.chat_report(arguments.id))
            elif arguments.command == 'chat-resolve':
                output = asdict(workflow.chat_resolve(arguments.id, outcome=arguments.outcome,
                                                     confirmed=arguments.confirm_checked))
            elif arguments.command == 'chat-import':
                imported = workflow.chat_import(arguments.ledger, confirmed=arguments.confirm_checked)
                output = asdict(imported) if imported else None
            elif arguments.command == 'scan':
                output = asdict(workflow.scan())
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
                workflow.assert_scan_channel('smtp')
                output = asdict(workflow.tick(first_scan=arguments.first_scan, notifier=SMTPNotifier.from_environment()))
            elif arguments.command == 'watch':
                workflow.assert_scan_channel('smtp')
                notifier = SMTPNotifier.from_environment()
                try:
                    while True:
                        result = workflow.tick(first_scan=arguments.first_scan, notifier=notifier)
                        if result.scanned:
                            print(json.dumps(asdict(result), ensure_ascii=False), flush=True)
                        time.sleep(60)
                except KeyboardInterrupt:
                    return 130
            elif arguments.command == 'scan-status':
                output = workflow.scan_status()
            elif arguments.command == 'notice-resolve':
                output = asdict(workflow.resolve_notice(arguments.id,
                    delivered=arguments.outcome == 'delivered', confirmed=arguments.confirm_checked))
            elif arguments.command == 'notices':
                output = [asdict(notice) for notice in workflow.notification_status()]
            elif arguments.command == 'instagram-check':
                output = {'account': asdict(workflow.check_instagram(InstagramConnection.from_environment())),
                          'publishing_permission': 'not_verified', 'published': False}
            else:
                raise WorkflowError('不支援的操作')
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (WorkflowError, OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
