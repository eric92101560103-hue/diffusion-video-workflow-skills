"""Public publishing workflow: the shared boundary for tools and background jobs."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import TracebackType
import hashlib
import fcntl
import os
import sqlite3
import uuid
from zoneinfo import ZoneInfo

from .media import inspect_video
from .instagram import Account, InstagramAccountReader
from .notifications import Notice, NoticeStatus, Notifier


class WorkflowError(Exception):
    """An actionable error safe to show without exposing credentials."""


@dataclass(frozen=True)
class Config:
    database: Path
    source: Path
    published: Path
    stable_seconds: int = 10


@dataclass(frozen=True)
class Candidate:
    id: str
    path: str
    fingerprint: str
    status: str
    caption: str | None
    revision: int
    scheduled_for: str | None
    approval_revision: int | None


@dataclass(frozen=True)
class ScanResult:
    discovered: tuple[Candidate, ...]
    skipped: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TickResult:
    scanned: bool
    discovered: tuple[Candidate, ...]
    next_scan: str
    notifications: tuple[NoticeStatus, ...]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fingerprint(path: Path) -> str:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ):
        raise WorkflowError('影片仍在變動，稍後再掃描')
    return digest.hexdigest()


class Workflow:
    def __init__(
        self,
        config: Config,
        *,
        now: Callable[[], datetime] = utc_now,
        inspect_media: Callable[[Path], None] = inspect_video,
    ) -> None:
        self.config = config
        self.now = now
        self.inspect_media = inspect_media
        if now().tzinfo is None:
            raise WorkflowError('時鐘必須包含時區')
        source, published = config.source.resolve(), config.published.resolve()
        if source == published or source in published.parents or published in source.parents:
            raise WorkflowError('待發佈與已發佈資料夾必須互不包含')
        if config.stable_seconds < 0:
            raise WorkflowError('檔案穩定時間不能小於零')
        config.database.parent.mkdir(parents=True, exist_ok=True)
        # Keep local state private; never store tokens in this database.
        descriptor = os.open(config.database, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        self.db = sqlite3.connect(config.database, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate',
                caption TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS archive_evidence (
                fingerprint TEXT PRIMARY KEY,
                path TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notices (
                candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),
                status TEXT NOT NULL
            );
        ''')
        columns = {str(row['name']) for row in self.db.execute('PRAGMA table_info(candidates)')}
        for column, definition in {
            'revision': 'INTEGER NOT NULL DEFAULT 1',
            'scheduled_for': 'TEXT',
            'approval_revision': 'INTEGER',
        }.items():
            if column not in columns:
                self.db.execute(f'ALTER TABLE candidates ADD COLUMN {column} {definition}')

    def __enter__(self) -> 'Workflow':
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc_value: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        self.db.close()

    @staticmethod
    def _candidate(row: sqlite3.Row) -> Candidate:
        return Candidate(
            str(row['id']), str(row['path']), str(row['fingerprint']),
            str(row['status']), None if row['caption'] is None else str(row['caption']),
            int(row['revision']),
            None if row['scheduled_for'] is None else str(row['scheduled_for']),
            None if row['approval_revision'] is None else int(row['approval_revision']),
        )

    def get(self, candidate_id: str) -> Candidate:
        row = self.db.execute('SELECT * FROM candidates WHERE id = ?', (candidate_id,)).fetchone()
        if row is None:
            raise WorkflowError('找不到候選影片')
        return self._candidate(row)

    def list_candidates(self) -> list[Candidate]:
        rows = self.db.execute('SELECT * FROM candidates ORDER BY created_at, id').fetchall()
        return [self._candidate(row) for row in rows]

    def check_instagram(self, connection: InstagramAccountReader) -> Account:
        account = connection.account()
        if account.username.casefold() != '_eric_han':
            raise WorkflowError('授權帳號不符；僅允許指定的 @_eric_han')
        return account

    def notification_status(self) -> list[NoticeStatus]:
        return [NoticeStatus(str(row['candidate_id']), str(row['status']))
                for row in self.db.execute('SELECT * FROM notices ORDER BY candidate_id')]

    def tick(self, *, first_scan: datetime, notifier: Notifier) -> TickResult:
        if first_scan.tzinfo is None:
            raise WorkflowError('首次掃描時間必須包含時區')
        # One local worker owns discovery + delivery at a time, including across restarts.
        # The lock is released by the OS if the process exits unexpectedly.
        lockfile = self.config.database.with_name(self.config.database.name + '.scan.lock')
        with lockfile.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            anchor = first_scan.astimezone(ZoneInfo('Asia/Taipei'))
            stored = self.db.execute("SELECT value FROM settings WHERE name = 'scan_anchor'").fetchone()
            if stored and str(stored['value']) != anchor.isoformat():
                raise WorkflowError('首次掃描時間已固定，請沿用既有設定')
            self.db.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', ('scan_anchor', anchor.isoformat()))
            next_setting = self.db.execute("SELECT value FROM settings WHERE name = 'next_scan'").fetchone()
            next_scan = datetime.fromisoformat(str(next_setting['value'])) if next_setting else anchor
            now = self.now()
            discovered: tuple[Candidate, ...] = ()
            scanned = now >= next_scan
            if scanned:
                result = self.scan()
                discovered = result.discovered
                while next_scan <= now:
                    next_scan += timedelta(days=2)
                self.db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ('next_scan', next_scan.isoformat()))
            for candidate in self.list_candidates():
                if candidate.status == 'candidate':
                    self.db.execute('INSERT OR IGNORE INTO notices VALUES (?, ?)', (candidate.id, 'pending'))
            pending = self.db.execute("SELECT candidate_id FROM notices WHERE status = 'pending'").fetchall()
            # A previous interrupted send may have been accepted by SMTP. Do not resend blindly.
            self.db.execute("UPDATE notices SET status = 'unknown' WHERE status = 'sending'")
            for row in pending:
                candidate = self.get(str(row['candidate_id']))
                if candidate.status != 'candidate':
                    self.db.execute("UPDATE notices SET status = 'obsolete' WHERE candidate_id = ?", (candidate.id,))
                    continue
                self.db.execute("UPDATE notices SET status = 'sending' WHERE candidate_id = ?", (candidate.id,))
                try:
                    notifier.send(Notice(candidate.id, Path(candidate.path).name))
                except Exception:
                    # No raw SMTP error: it can include credentials or personal server configuration.
                    status = 'unknown'
                else:
                    status = 'sent'
                self.db.execute('UPDATE notices SET status = ? WHERE candidate_id = ?', (status, candidate.id))
            return TickResult(scanned, discovered, next_scan.isoformat(), tuple(self.notification_status()))

    def set_caption(self, candidate_id: str, caption: str) -> Candidate:
        candidate = self.get(candidate_id)
        if candidate.status not in ('candidate', 'approved'):
            raise WorkflowError('目前狀態不能修改文案')
        if caption != candidate.caption:
            self.db.execute(
                "UPDATE candidates SET caption = ?, revision = revision + 1, "
                "status = 'candidate', approval_revision = NULL WHERE id = ?",
                (caption, candidate_id),
            )
        return self.get(candidate_id)

    def _check_video(self, candidate: Candidate) -> None:
        path = Path(candidate.path)
        try:
            if path.is_symlink() or path.resolve().parent != self.config.source.resolve():
                raise WorkflowError('影片已移出待發佈資料夾，請重新確認')
            before = path.stat()
            if self.now().timestamp() - before.st_mtime < self.config.stable_seconds:
                raise WorkflowError('影片仍在變動，請稍後重新確認')
            self.inspect_media(path)
            if fingerprint(path) != candidate.fingerprint:
                raise WorkflowError('影片內容已變更，請重新掃描及核准')
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                after.st_size, after.st_mtime_ns, after.st_ino
            ):
                raise WorkflowError('影片仍在變動，請稍後重新確認')
        except (OSError, ValueError) as error:
            raise WorkflowError('影片不存在或無法驗證，請重新掃描') from error

    def preview(self, candidate_ids: Sequence[str], *, first_date: date | None = None) -> list[Candidate]:
        if not candidate_ids or len(set(candidate_ids)) != len(candidate_ids):
            raise WorkflowError('請提供不重複的候選影片順序')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            candidates = [self.get(candidate_id) for candidate_id in candidate_ids]
            if any(candidate.status not in ('candidate', 'approved') for candidate in candidates):
                raise WorkflowError('只能安排尚未啟用的候選影片')
            for candidate in candidates:
                self._check_video(candidate)
            setting = self.db.execute("SELECT value FROM settings WHERE name = 'first_date'").fetchone()
            if setting is None:
                if first_date is None:
                    raise WorkflowError('首次安排請指定首發日期')
                anchor = first_date
                self.db.execute('INSERT INTO settings VALUES (?, ?)', ('first_date', anchor.isoformat()))
            else:
                anchor = date.fromisoformat(str(setting['value']))
                if first_date is not None and first_date != anchor:
                    raise WorkflowError('首發日期已固定；新增批次沿用原本隔日節奏')
            cutoff = self.now().astimezone(ZoneInfo('Asia/Taipei'))
            for existing in self.list_candidates():
                if existing.id not in candidate_ids and existing.status in (
                    'approved', 'active', 'publishing', 'unknown', 'published'
                ) and existing.scheduled_for:
                    cutoff = max(cutoff, datetime.fromisoformat(existing.scheduled_for))
            slot = datetime.combine(anchor, time(20), tzinfo=ZoneInfo('Asia/Taipei'))
            while slot <= cutoff:
                slot += timedelta(days=2)
            for candidate in candidates:
                if candidate.scheduled_for != slot.isoformat():
                    self.db.execute(
                        "UPDATE candidates SET scheduled_for = ?, revision = revision + 1, "
                        "status = 'candidate', approval_revision = NULL WHERE id = ?",
                        (slot.isoformat(), candidate.id),
                    )
                slot += timedelta(days=2)
            self.db.execute('COMMIT')
        except (WorkflowError, sqlite3.Error, ValueError, OverflowError):
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
        return [self.get(candidate_id) for candidate_id in candidate_ids]

    def approve(self, revisions: Mapping[str, int]) -> list[Candidate]:
        if not revisions:
            raise WorkflowError('請指定已審核的影片與版本')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            candidates = [self.get(candidate_id) for candidate_id in revisions]
            slots: set[str] = set()
            for candidate in candidates:
                if candidate.revision != revisions[candidate.id]:
                    raise WorkflowError('清單版本已改變，請重新查看與確認')
                if candidate.status not in ('candidate', 'approved'):
                    raise WorkflowError('目前狀態不能核准')
                if not candidate.caption or not candidate.caption.strip():
                    raise WorkflowError('請先填寫發佈文案')
                if not candidate.scheduled_for:
                    raise WorkflowError('請先查看候選排程')
                if datetime.fromisoformat(candidate.scheduled_for) <= self.now():
                    raise WorkflowError('候選日期已過，請重新查看排程後再確認')
                if candidate.scheduled_for in slots:
                    raise WorkflowError('同一個時段不能安排兩支影片')
                slots.add(candidate.scheduled_for)
                collision = self.db.execute(
                    "SELECT id FROM candidates WHERE scheduled_for = ? AND id != ? "
                    "AND status IN ('approved', 'active', 'publishing', 'unknown', 'published')",
                    (candidate.scheduled_for, candidate.id),
                ).fetchone()
                if collision and str(collision['id']) not in revisions:
                    raise WorkflowError('時段已被其他安排使用，請重新查看排程')
                self._check_video(candidate)
            for candidate in candidates:
                self.db.execute(
                    "UPDATE candidates SET status = 'approved', approval_revision = revision WHERE id = ?",
                    (candidate.id,),
                )
            self.db.execute('COMMIT')
        except (WorkflowError, sqlite3.Error):
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
        return [self.get(candidate.id) for candidate in candidates]

    def replay(self, path: Path, *, confirmed: bool = False) -> Candidate:
        if not confirmed:
            raise WorkflowError('重發必須由使用者明確確認')
        if path.is_symlink() or path.resolve().parent != self.config.source.resolve():
            raise WorkflowError('只能重發指定待發佈資料夾內的一般影片')
        before = path.stat()
        if path.suffix.lower() not in ('.mp4', '.mov') or before.st_size == 0:
            raise WorkflowError('請選擇完整影片')
        if self.now().timestamp() - before.st_mtime < self.config.stable_seconds:
            raise WorkflowError('影片仍在複製或尚未穩定')
        self.inspect_media(path)
        digest = fingerprint(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino
        ):
            raise WorkflowError('影片仍在變動，稍後再試')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            pending = self.db.execute(
                "SELECT id FROM candidates WHERE fingerprint = ? AND status IN ('candidate', 'approved')",
                (digest,),
            ).fetchone()
            if pending:
                raise WorkflowError('相同影片已有待審或已核准項目')
            candidate_id = uuid.uuid4().hex
            self.db.execute(
                'INSERT INTO candidates (id, path, fingerprint, created_at) VALUES (?, ?, ?, ?)',
                (candidate_id, str(path.resolve()), digest, self.now().isoformat()),
            )
            self.db.execute('COMMIT')
        except (sqlite3.Error, WorkflowError):
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
        return self.get(candidate_id)

    def scan(self) -> ScanResult:
        if not self.config.source.is_dir():
            raise WorkflowError('待發佈資料夾不存在或無法讀取')
        if not self.config.published.is_dir():
            raise WorkflowError('已發佈資料夾不存在，無法先比對既有成片')
        discovered: list[Candidate] = []
        skipped: list[tuple[str, str]] = []
        try:
            archive = sorted(self.config.published.iterdir())
            sources = sorted(self.config.source.iterdir())
            self.db.execute('BEGIN IMMEDIATE')
            for path in archive:
                if path.suffix.lower() in ('.mp4', '.mov') and path.is_file() and not path.is_symlink():
                    digest = fingerprint(path)
                    self.db.execute(
                        'INSERT OR IGNORE INTO archive_evidence VALUES (?, ?)', (digest, str(path)),
                    )
            for path in sources:
                if path.name.startswith('.') or path.suffix.lower() not in ('.mp4', '.mov'):
                    continue
                try:
                    if path.is_symlink() or not path.is_file():
                        raise WorkflowError('略過連結或非一般影片檔案')
                    before = path.stat()
                    if before.st_size == 0 or self.now().timestamp() - before.st_mtime < self.config.stable_seconds:
                        raise WorkflowError('影片仍在複製或尚未穩定')
                    self.inspect_media(path)
                    digest = fingerprint(path)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                        after.st_size, after.st_mtime_ns, after.st_ino
                    ):
                        raise WorkflowError('影片仍在變動，稍後再掃描')
                    previous = self.db.execute(
                        'SELECT id, path, status FROM candidates WHERE fingerprint = ? LIMIT 1', (digest,),
                    ).fetchone()
                    archived = self.db.execute(
                        'SELECT path FROM archive_evidence WHERE fingerprint = ?', (digest,),
                    ).fetchone()
                    if previous or archived:
                        if previous and previous['status'] == 'candidate' and not Path(previous['path']).exists():
                            self.db.execute(
                                'UPDATE candidates SET path = ? WHERE id = ?',
                                (str(path.resolve()), previous['id']),
                            )
                        skipped.append((str(path), '內容重複；若要重發請明確建立重發候選'))
                        continue
                    candidate_id = uuid.uuid4().hex
                    self.db.execute(
                        'INSERT INTO candidates (id, path, fingerprint, created_at) VALUES (?, ?, ?, ?)',
                        (candidate_id, str(path.resolve()), digest, self.now().isoformat()),
                    )
                    discovered.append(self.get(candidate_id))
                except (OSError, ValueError, WorkflowError) as error:
                    skipped.append((str(path), str(error)))
            self.db.execute('COMMIT')
        except (OSError, sqlite3.Error, WorkflowError) as error:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise WorkflowError('掃描或既有成片比對失敗；未建立候選') from error
        return ScanResult(tuple(discovered), tuple(skipped))
