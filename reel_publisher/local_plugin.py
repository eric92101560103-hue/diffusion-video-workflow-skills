"""Read-only installation checks. No schedule, secret lookup, media scan or service start."""

from typing import TYPE_CHECKING
import os
import shutil
import sqlite3
import sys

if TYPE_CHECKING:
    from .workflow import Config


def preflight(config: 'Config') -> dict[str, object]:
    missing: list[str] = []
    if sys.version_info < (3, 11):
        missing.append('需要 Python 3.11 或更新版本')
    if not shutil.which('ffprobe'):
        missing.append('找不到 ffprobe，請先安裝 FFmpeg')
    for label, path in [('待發佈', config.source), ('已發佈', config.published)]:
        if not path.is_dir() or not os.access(path, os.R_OK | os.X_OK):
            missing.append(label + '資料夾不存在或無法讀取')
    source, published = config.source.resolve(), config.published.resolve()
    if source == published or source in published.parents or published in source.parents:
        missing.append('待發佈與已發佈資料夾必須互不包含')
    values: dict[str, str] = {}
    if config.database.exists():
        try:
            with sqlite3.connect(config.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
                names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                if 'settings' in names:
                    values = dict(db.execute("SELECT name, value FROM settings WHERE name IN "
                                             "('chat_first_scan', 'chat_enabled', 'scan_owner')"))
        except sqlite3.Error:
            missing.append('狀態資料庫無法讀取，請先修復或選擇正確資料庫')
    return {'runtime_ready': not missing, 'missing': missing,
            'configured': bool(values.get('chat_first_scan')),
            'enabled': values.get('chat_enabled') == 'true',
            'primary': values.get('scan_owner'),
            'scheduler': 'managed_in_codex', 'publishing_available': False,
            'credentials_required': False}
