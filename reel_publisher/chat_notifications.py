"""Durable handoff to a chat, separate from acknowledgement of receipt."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo
import fcntl
import hashlib
import json
import uuid

if TYPE_CHECKING:
    from .workflow import Workflow


@dataclass(frozen=True)
class ChatItem:
    kind: str
    reference: str
    message: str
    filename: str | None = None


@dataclass(frozen=True)
class ChatReport:
    id: str
    status: str
    items: tuple[ChatItem, ...]


@dataclass(frozen=True)
class ChatCheck:
    scanned: bool
    next_scan: str | None
    notification: ChatReport | None
    unconfirmed_report_ids: tuple[str, ...]
    scan_error: str | None = None


class ChatDelivery:
    def __init__(self, workflow: 'Workflow') -> None:
        self.workflow = workflow
        self.db = workflow.db

    def _get(self, key: str) -> str | None:
        row = self.db.execute('SELECT value FROM settings WHERE name = ?', (key,)).fetchone()
        return str(row['value']) if row else None

    def _set(self, key: str, value: str) -> None:
        self.db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, value))

    @contextmanager
    def _locked(self) -> Iterator[None]:
        path = self.workflow.config.database
        with path.with_name(path.name + '.scan.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def setup(self, first_scan: datetime) -> dict[str, object]:
        from .workflow import WorkflowError
        if first_scan.tzinfo is None:
            raise WorkflowError('首次掃描時間必須包含時區')
        anchor = first_scan.astimezone(ZoneInfo('Asia/Taipei')).isoformat()
        with self._locked(), self._transaction():
            existing = self._get('chat_first_scan')
            if existing and existing != anchor:
                raise WorkflowError('掃描節奏已配置；請沿用既有首次時間，不重設歷史')
            self._set('chat_first_scan', anchor)
            if not existing:
                self._set('chat_next_scan', anchor)
                self._set('chat_enabled', 'false')
                self._set('chat_source', str(self.workflow.config.source.resolve()))
                self._set('chat_published', str(self.workflow.config.published.resolve()))
        return self.status()

    def enable(self, confirmed: bool) -> dict[str, object]:
        from .workflow import WorkflowError
        if not confirmed or not self._get('chat_first_scan'):
            raise WorkflowError('請先配置並明確確認以 Codex 作為主要掃描來源')
        with self._locked(), self._transaction():
            if self._get('scan_owner') not in (None, 'codex'):
                raise WorkflowError('另一主要掃描通道仍持有此狀態；請先停用及交接')
            self._set('scan_owner', 'codex')
            self._set('chat_enabled', 'true')
        return self.status()

    def disable(self) -> dict[str, object]:
        with self._locked(), self._transaction():
            self._set('chat_enabled', 'false')
        return self.status()

    def release_primary(self, confirmed: bool) -> dict[str, object]:
        from .workflow import WorkflowError
        if not confirmed:
            raise WorkflowError('請先停止所有舊主要掃描器，再明確確認交接')
        with self._locked(), self._transaction():
            self._set('chat_enabled', 'false')
            self.db.execute("DELETE FROM settings WHERE name = 'scan_owner'")
        return self.status()

    def status(self) -> dict[str, object]:
        return {'configured': bool(self._get('chat_first_scan')),
                'enabled': self._get('chat_enabled') == 'true',
                'primary': self._get('scan_owner'),
                'first_scan': self._get('chat_first_scan'), 'next_scan': self._get('chat_next_scan'),
                'unconfirmed_report_ids': [str(row['id']) for row in self.db.execute(
                    "SELECT id FROM chat_reports WHERE status = 'unconfirmed' ORDER BY rowid")],
                'last_success': self._get('chat_last_success'), 'scan_error': self._get('chat_error_code'),
                'scheduler': 'managed_in_codex', 'publishing_available': False}

    def report(self, report_id: str) -> ChatReport:
        from .workflow import WorkflowError
        row = self.db.execute('SELECT * FROM chat_reports WHERE id = ?', (report_id,)).fetchone()
        if not row:
            raise WorkflowError('找不到通知回報')
        return ChatReport(str(row['id']), str(row['status']),
                          tuple(ChatItem(**item) for item in json.loads(row['payload'])))

    def import_legacy(self, path: Path, confirmed: bool) -> ChatReport | None:
        from .workflow import WorkflowError
        if not confirmed:
            raise WorkflowError('匯入前請確認這是本狀態資料庫對應的舊通知紀錄')
        try:
            if path.stat().st_size > 1_000_000:
                raise ValueError('too large')
            data = json.loads(path.read_text())
            ids = data['reported_candidate_ids']
            if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
                raise ValueError('invalid IDs')
            if len(set(ids)) != len(ids):
                raise ValueError('duplicate IDs')
        except (OSError, ValueError, KeyError, TypeError):
            raise WorkflowError('舊通知紀錄無效，未匯入；請檢查 JSON 與候選 ID 清單') from None
        if not ids:
            return None
        report_id = 'legacy-' + hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest()
        with self._locked(), self._transaction():
            candidates = [self.workflow.get(candidate_id) for candidate_id in ids]
            if self.db.execute('SELECT id FROM chat_reports WHERE id = ?', (report_id,)).fetchone():
                return self.report(report_id)
            items = []
            for candidate in candidates:
                key = 'candidate:' + candidate.id
                if self.db.execute('SELECT event_key FROM chat_events WHERE event_key = ?', (key,)).fetchone():
                    continue
                items.append(ChatItem('candidate', candidate.id, '舊紀錄曾產生提醒，實際送達尚未確認',
                                      Path(candidate.path).name))
            if not items:
                return None
            self.db.execute("INSERT INTO chat_reports VALUES (?, 'unconfirmed', ?)",
                            (report_id, json.dumps([asdict(item) for item in items], ensure_ascii=False)))
            for item in items:
                self.db.execute("INSERT INTO chat_events VALUES (?, ?, 'unconfirmed', ?)",
                                ('candidate:' + item.reference, json.dumps(asdict(item), ensure_ascii=False), report_id))
            return self.report(report_id)

    def check(self) -> ChatCheck:
        from .workflow import WorkflowError
        with self._locked():
            if self._get('chat_enabled') != 'true' or self._get('scan_owner') != 'codex':
                raise WorkflowError('Codex 掃描未啟用；請先查看設定及主要掃描通道')
            if (self._get('chat_source') != str(self.workflow.config.source.resolve()) or
                    self._get('chat_published') != str(self.workflow.config.published.resolve())):
                raise WorkflowError('來源與已配置路徑不同，請沿用相同狀態及來源')
            next_scan = datetime.fromisoformat(self._get('chat_next_scan') or '')
            scanned = self.workflow.now() >= next_scan
            error_code: str | None = None
            if scanned:
                try:
                    self.workflow.scan()
                except (WorkflowError, OSError):
                    if not self.workflow.config.source.is_dir():
                        error_code = 'source_unavailable'
                    elif not self.workflow.config.published.is_dir():
                        error_code = 'archive_unavailable'
                    else:
                        error_code = 'scan_unavailable'
                else:
                    while next_scan <= self.workflow.now():
                        next_scan += timedelta(days=2)
            with self._transaction():
                previous_fault = self._get('chat_fault')
                if scanned and error_code:
                    if self._get('chat_error_code') != error_code:
                        fault = 'fault:' + uuid.uuid4().hex
                        messages = {'source_unavailable': '待發佈資料夾不存在或無法讀取，請恢復存取',
                                    'archive_unavailable': '已發佈資料夾不存在或無法讀取，無法比對既有成片',
                                    'scan_unavailable': '本機掃描失敗，請檢查檔案存取及狀態'}
                        item = ChatItem('failure', fault, messages[error_code])
                        self.db.execute('INSERT INTO chat_events VALUES (?, ?, ?, NULL)',
                                        (fault, json.dumps(asdict(item), ensure_ascii=False), 'pending'))
                        self._set('chat_fault', fault)
                        self._set('chat_error_code', error_code)
                elif scanned:
                    self._set('chat_next_scan', next_scan.isoformat())
                    self._set('chat_last_success', self.workflow.now().isoformat())
                    if previous_fault:
                        item = ChatItem('recovery', previous_fault, '本機掃描已恢復，已補掃一次')
                        self.db.execute('INSERT OR IGNORE INTO chat_events VALUES (?, ?, ?, NULL)',
                                        ('recovery:' + previous_fault, json.dumps(asdict(item), ensure_ascii=False), 'pending'))
                        self.db.execute("DELETE FROM settings WHERE name IN ('chat_fault', 'chat_error_code')")
                for candidate in self.workflow.list_candidates():
                    if candidate.status != 'candidate':
                        self.db.execute("UPDATE chat_events SET status = 'obsolete' WHERE event_key = ? AND status = 'pending'",
                                        ('candidate:' + candidate.id,))
                    else:
                        item = ChatItem('candidate', candidate.id, '發現待審影片，請填文案並確認順序與日期',
                                        Path(candidate.path).name)
                        self.db.execute('INSERT OR IGNORE INTO chat_events VALUES (?, ?, ?, NULL)',
                                        ('candidate:' + candidate.id, json.dumps(asdict(item), ensure_ascii=False), 'pending'))
                        self.db.execute("UPDATE chat_events SET payload = ? WHERE event_key = ? AND status = 'pending'",
                                        (json.dumps(asdict(item), ensure_ascii=False), 'candidate:' + candidate.id))
                rows = self.db.execute("SELECT * FROM chat_events WHERE status = 'pending' ORDER BY rowid").fetchall()
                report: ChatReport | None = None
                if rows:
                    report_id = uuid.uuid4().hex
                    payload = '[' + ','.join(str(row['payload']) for row in rows) + ']'
                    self.db.execute("INSERT INTO chat_reports VALUES (?, 'unconfirmed', ?)", (report_id, payload))
                    self.db.execute("UPDATE chat_events SET status = 'unconfirmed', report_id = ? WHERE status = 'pending'", (report_id,))
                    report = self.report(report_id)
            unconfirmed = tuple(str(row['id']) for row in self.db.execute(
                "SELECT id FROM chat_reports WHERE status = 'unconfirmed' ORDER BY rowid"))
            return ChatCheck(scanned and error_code is None, next_scan.isoformat(), report, unconfirmed, error_code)

    def resolve(self, report_id: str, outcome: Literal['received', 'not-delivered'], confirmed: bool) -> ChatReport:
        from .workflow import WorkflowError
        if not confirmed or outcome not in ('received', 'not-delivered'):
            raise WorkflowError('須先核對回報結果並明確確認；產生文字不代表已送達')
        with self._locked(), self._transaction():
            report = self.report(report_id)
            if report.status == outcome:
                return report
            if report.status != 'unconfirmed':
                raise WorkflowError('此回報已有不同核對結果，請先查閱紀錄')
            self.db.execute('UPDATE chat_reports SET status = ? WHERE id = ?', (outcome, report_id))
            status = 'received' if outcome == 'received' else 'pending'
            self.db.execute('UPDATE chat_events SET status = ? WHERE report_id = ?', (status, report_id))
            return self.report(report_id)
