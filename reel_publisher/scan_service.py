"""Prepare an inactive launchd bundle; activation remains an explicit operator action."""

from datetime import datetime
from pathlib import Path
import json
import os
import plistlib
import shlex
import sys

from .workflow import Config, WorkflowError

LABEL = 'local.reel-publisher.scan'
SMTP_SETTINGS = frozenset({
    'REEL_SMTP_HOST', 'REEL_SMTP_PORT', 'REEL_EMAIL_FROM', 'REEL_EMAIL_TO',
    'REEL_SMTP_USERNAME', 'REEL_SMTP_KEYCHAIN_SERVICE',
})


def prepare(config: Config, directory: Path, first_scan: datetime) -> dict[str, object]:
    if first_scan.tzinfo is None:
        raise WorkflowError('首次掃描時間必須包含時區')
    directory = directory.absolute()
    if directory.exists():
        raise WorkflowError('服務準備目錄已存在；請選擇新目錄，避免覆寫已審閱設定')
    directory.mkdir(mode=0o700, parents=True)
    settings = {
        'source': str(config.source.absolute()), 'published': str(config.published.absolute()),
        'database': str(config.database.absolute()), 'first_scan': first_scan.isoformat(),
        'smtp': {},
    }
    settings_path = directory / 'settings.json'
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + '\n')
    settings_path.chmod(0o600)
    arguments = [sys.executable, '-m', 'reel_publisher.scan_service', str(settings_path)]
    plist = directory / f'{LABEL}.plist'
    plist.write_bytes(plistlib.dumps({
        'Label': LABEL, 'ProgramArguments': arguments,
        'WorkingDirectory': str(Path(__file__).resolve().parent.parent),
        'RunAtLoad': True, 'StartInterval': 60, 'ProcessType': 'Background',
        'StandardOutPath': str(directory / 'scan.log'),
        'StandardErrorPath': str(directory / 'scan-error.log'),
        'Umask': 0o077,
    }))
    plist.chmod(0o600)
    check = shlex.join(arguments + ['--check'])
    enable = f'''#!/bin/sh
set -eu
[ "${{1:-}}" = "--confirm-enable" ] || {{ echo '需先審閱設定並確認啟用：--confirm-enable' >&2; exit 2; }}
{check}
target="$HOME/Library/LaunchAgents/{LABEL}.plist"
mkdir -p "$HOME/Library/LaunchAgents"
[ ! -e "$target" ] || {{ echo '已存在同名服務設定；請先核對或停用，不覆寫' >&2; exit 1; }}
set -C
cat {shlex.quote(str(plist))} > "$target"
set +C
chmod 600 "$target"
launchctl bootstrap "gui/$(id -u)" "$target"
launchctl print "gui/$(id -u)/{LABEL}"
'''
    disable = f'''#!/bin/sh
set -eu
target="$HOME/Library/LaunchAgents/{LABEL}.plist"
[ -f "$target" ] || {{ echo '找不到此 bundle 的已安裝設定，未操作服務' >&2; exit 1; }}
cmp -s {shlex.quote(str(plist))} "$target" || {{ echo '設定與此 bundle 不同，拒絕停用或刪除' >&2; exit 1; }}
if launchctl print "gui/$(id -u)/{LABEL}" >/dev/null 2>&1; then
    launchctl bootout "gui/$(id -u)/{LABEL}"
fi
rm "$target"
'''
    for name, content in [('enable.sh', enable), ('disable.sh', disable)]:
        path = directory / name
        path.write_text(content)
        path.chmod(0o700)
    return {'directory': str(directory), 'enabled': False, 'settings_required': True,
            'scope': 'local_scan_only'}


def run(settings_path: Path, *, check: bool = False) -> int:
    """One short tick per launchd trigger; missed calendar slots collapse to one scan."""
    from .cli import main
    try:
        settings = json.loads(settings_path.read_text())
        for key in ('source', 'published', 'database'):
            if not Path(settings[key]).is_absolute():
                raise ValueError('路徑必須是絕對路徑')
        smtp = settings['smtp']
        if not isinstance(smtp, dict) or any(
            key not in SMTP_SETTINGS or not isinstance(value, str) for key, value in smtp.items()
        ):
            raise ValueError('只允許非秘密 SMTP 設定；密碼請使用明確指定的 Keychain 項目')
        if not all(smtp.get(key) for key in (
            'REEL_SMTP_HOST', 'REEL_EMAIL_FROM', 'REEL_EMAIL_TO',
            'REEL_SMTP_USERNAME', 'REEL_SMTP_KEYCHAIN_SERVICE',
        )):
            raise ValueError('尚缺寄信主機、寄收件地址、使用者名稱或 Keychain 服務名稱')
        port = int(smtp.get('REEL_SMTP_PORT', '465'))
        if not 1 <= port <= 65535:
            raise ValueError('SMTP 連線埠無效')
        first_scan = datetime.fromisoformat(settings['first_scan'])
        if first_scan.tzinfo is None:
            raise ValueError('首次掃描時間必須包含時區')
        for key in ('source', 'published'):
            if not Path(settings[key]).is_dir():
                raise ValueError('掃描與歸檔資料夾必須存在')
        if check:
            print(json.dumps({'configuration': 'valid', 'credentials': 'not_checked',
                              'enabled': False, 'email_sent': False}))
            return 0
        # Do not inherit unrelated SMTP settings or a plaintext password from a shell.
        for key in SMTP_SETTINGS | {'REEL_SMTP_PASSWORD'}:
            os.environ.pop(key, None)
        os.environ.update(smtp)
        return main(['--source', settings['source'], '--published', settings['published'],
                     '--database', settings['database'], 'tick',
                     '--first-scan', first_scan.isoformat()])
    except (OSError, ValueError, KeyError, TypeError):
        # Never expose input values, addresses, or secrets in background logs.
        print('掃描服務設定無效或未齊全；請檢查私有 settings.json，尚未寄信', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != '--check'):
        raise SystemExit('usage: python -m reel_publisher.scan_service SETTINGS [--check]')
    raise SystemExit(run(Path(sys.argv[1]), check=len(sys.argv) == 3))
