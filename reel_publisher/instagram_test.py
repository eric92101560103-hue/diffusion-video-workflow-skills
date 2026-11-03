"""Durable one-off test releases, distinct from continuous/cloud scheduling."""
from dataclasses import dataclass
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
import fcntl
import hashlib
import os
import re
import uuid

from .instagram_publishing import FacebookReels
from .media import inspect_reel_video

if TYPE_CHECKING:
    from .workflow import Workflow


@dataclass(frozen=True)
class InstagramTest:
    id: str
    candidate_id: str
    revision: int
    fingerprint: str
    path: str
    caption: str
    page_id: str
    account_id: str
    version: str
    status: str
    container_id: str | None
    media_id: str | None
    permalink: str | None
    approved_at: str | None
    next_check_at: str | None
    reason: str | None
    scheduled_for: str | None
    timing: str = 'immediately_after_explicit_approval'


class InstagramTests:
    def __init__(self, workflow: 'Workflow') -> None:
        self.workflow = workflow
        self.db = workflow.db
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('''CREATE TABLE IF NOT EXISTS instagram_tests (
            id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidates(id),
            revision INTEGER NOT NULL, fingerprint TEXT NOT NULL, path TEXT NOT NULL,
            caption TEXT NOT NULL, page_id TEXT NOT NULL, account_id TEXT NOT NULL,
            version TEXT NOT NULL, status TEXT NOT NULL, container_id TEXT, media_id TEXT,
            permalink TEXT, approved_at TEXT, next_check_at TEXT, reason TEXT,
            processing_started_at TEXT, UNIQUE(candidate_id, revision)
            )''')
            columns = {str(row['name']) for row in self.db.execute('PRAGMA table_info(instagram_tests)')}
            if 'scheduled_for' not in columns:
                self.db.execute('ALTER TABLE instagram_tests ADD COLUMN scheduled_for TEXT')
            self.db.execute('COMMIT')
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
        self.directory = workflow.config.database.parent / 'instagram-test-media'

    def get(self, job_id: str) -> InstagramTest:
        row = self.db.execute('SELECT * FROM instagram_tests WHERE id = ?', (job_id,)).fetchone()
        if row is None:
            raise ValueError('找不到單支 IG 測試')
        return InstagramTest(**{name: row[name] for name in InstagramTest.__dataclass_fields__ if name != 'timing'},
                             timing='at_approved_time' if row['scheduled_for'] else 'immediately_after_explicit_approval')

    def _check(self, job: InstagramTest) -> None:
        candidate = self.workflow.get(job.candidate_id)
        if (candidate.status not in ('candidate', 'test_in_progress') or candidate.revision != job.revision
                or candidate.fingerprint != job.fingerprint or candidate.caption != job.caption
                or candidate.path != job.path):
            raise ValueError('單支測試的影片或文案版本已變更，需重新審核')
        self.workflow._check_video(candidate)

    def _save(self, job_id: str, status: str, reason: str | None = None) -> InstagramTest:
        self.db.execute('UPDATE instagram_tests SET status = ?, reason = ? WHERE id = ?',
                        (status, reason, job_id))
        return self.get(job_id)

    @contextmanager
    def _lock(self) -> Iterator[None]:
        with self.workflow.config.database.with_suffix('.instagram-test.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def cancel(self, job_id: str, confirmed: bool) -> InstagramTest:
        if not confirmed:
            raise ValueError('取消單支測試需要明確確認')
        with self._lock():
            job = self.get(job_id)
            if job.status in ('unknown', 'publishing', 'published', 'cancelled'):
                return job
            try:
                self.db.execute('BEGIN IMMEDIATE')
                self._save(job.id, 'cancelled', '單支測試已取消；不刪除媒體或遠端容器')
                self.db.execute("UPDATE candidates SET status = 'candidate', revision = revision + 1, approval_revision = NULL "
                                "WHERE id = ? AND status IN ('candidate', 'test_in_progress') AND revision = ?",
                                (job.candidate_id, job.revision))
                self.db.execute('COMMIT')
            except BaseException:
                if self.db.in_transaction:
                    self.db.execute('ROLLBACK')
                raise
            return self.get(job_id)

    def schedule(self, job_id: str, due: datetime, confirmed: bool) -> InstagramTest:
        if not confirmed or due.tzinfo is None or not self.workflow.now() < due <= self.workflow.now() + timedelta(days=1):
            raise ValueError('單支驗收需明確核准含時區且未來24小時內的發佈時間')
        with self._lock():
            job = self.get(job_id)
            if job.status == 'scheduled' and job.scheduled_for == due.isoformat():
                return job
            if job.status != 'awaiting_approval':
                raise ValueError('只有待核准的單支驗收可設定時間；修改需先取消並重新審核')
            try:
                self.db.execute('BEGIN IMMEDIATE')
                self._check(job)
                self.db.execute("UPDATE candidates SET status = 'test_in_progress', approval_revision = NULL WHERE id = ?",
                                (job.candidate_id,))
                self.db.execute("UPDATE instagram_tests SET status = 'scheduled', scheduled_for = ?, approved_at = ?, "
                                "next_check_at = ? WHERE id = ?", (due.isoformat(), self.workflow.now().isoformat(),
                                (due - timedelta(minutes=10)).isoformat(), job.id))
                self.db.execute('COMMIT')
            except BaseException:
                if self.db.in_transaction:
                    self.db.execute('ROLLBACK')
                raise
            return self.get(job.id)

    def _cutoff(self, job: InstagramTest) -> datetime:
        anchor = job.scheduled_for or job.approved_at
        if not anchor:
            raise ValueError('缺少可核對的核准時間')
        return datetime.fromisoformat(anchor) + timedelta(minutes=30)

    def prepare(self, candidate_id: str, revision: int, page_id: str, version: str) -> InstagramTest:
        if not re.fullmatch(r'[0-9]{1,64}', page_id) or not re.fullmatch(r'v[0-9]+\.0', version):
            raise ValueError('請提供已核對的專頁與 API 版本')
        item = self.workflow.get(candidate_id)
        if item.status != 'candidate' or item.revision != revision or not item.caption or not item.caption.strip():
            raise ValueError('單支測試需最新待審候選與完整文案，不沿用既有排程核准')
        if len(item.caption) > 2200:
            raise ValueError('發佈文案超過 2200 字元')
        self.workflow._check_video(item)
        inspect_reel_video(Path(item.path))
        existing = self.db.execute('SELECT id FROM instagram_tests WHERE candidate_id = ? AND revision = ?',
                                   (candidate_id, revision)).fetchone()
        if existing:
            return self.get(str(existing['id']))
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink():
            raise ValueError('測試影片暫存位置不能是連結')
        job_id = uuid.uuid4().hex
        target = self.directory / f'{job_id}.media'
        digest = hashlib.sha256()
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as output, Path(item.path).open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest() != item.fingerprint:
                raise ValueError('影片內容已變更，請重新掃描及審核')
            self.db.execute('''INSERT INTO instagram_tests
                (id,candidate_id,revision,fingerprint,path,caption,page_id,account_id,version,status)
                VALUES (?,?,?,?,?,?,?,?,?,'awaiting_approval')''',
                (job_id, item.id, item.revision, item.fingerprint, item.path, item.caption,
                 page_id, '17841403997461963', version))
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return self.get(job_id)

    def publish(self, job_id: str, publisher: FacebookReels, confirmed: bool) -> InstagramTest:
        with self._lock():
            job = self.get(job_id)
            ready_checked = False
            if not confirmed and not (job.scheduled_for and job.approved_at):
                raise ValueError('需明確核准此單支測試的影片、文案及發佈時間')
            if job.status in ('published', 'unknown', 'blocked', 'cancelled'):
                return job
            if job.status in ('creating', 'uploading', 'publishing'):
                return self._save(job.id, 'unknown' if job.status == 'publishing' else 'blocked',
                                  '先前操作中斷；停止重送，需人工核對')
            if job.scheduled_for:
                due = datetime.fromisoformat(job.scheduled_for)
                if self.workflow.now() < due - timedelta(minutes=10):
                    return job
                if job.status == 'ready' and self.workflow.now() < due:
                    return job
            self._check(job)
            if (publisher.account_id, publisher.page_id, publisher.version) != (job.account_id, job.page_id, job.version):
                raise ValueError('發佈配置與審核快照不符')
            if job.approved_at and self.workflow.now() >= self._cutoff(job):
                return self._save(job.id, 'blocked', '已超過核准發佈時間30分鐘，需重新審核')
            self.workflow.check_instagram(publisher)
            if job.status == 'awaiting_approval':
                try:
                    self.db.execute('BEGIN IMMEDIATE')
                    self._check(job)
                    self.db.execute("UPDATE candidates SET status = 'test_in_progress', approval_revision = NULL WHERE id = ?",
                                    (job.candidate_id,))
                    self.db.execute("UPDATE instagram_tests SET approved_at = ?, status = 'approved' WHERE id = ?",
                                    (self.workflow.now().isoformat(), job.id))
                    self.db.execute('COMMIT')
                except BaseException:
                    if self.db.in_transaction:
                        self.db.execute('ROLLBACK')
                    raise
                job = self.get(job.id)
            if job.status in ('approved', 'scheduled'):
                self._save(job.id, 'creating')
                try:
                    target = self.directory / f'{job.id}.media'
                    if self.directory.is_symlink() or target.is_symlink():
                        raise ValueError('暫存影片位置已變更')
                    with os.fdopen(os.open(target, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
                        copied = hashlib.sha256()
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            copied.update(block)
                        if copied.hexdigest() != job.fingerprint:
                            raise ValueError('暫存內容與核准影片不符')
                        stream.seek(0)
                        container_id = publisher.create(job.caption)
                        self.db.execute("UPDATE instagram_tests SET container_id = ?, status = 'uploading' WHERE id = ?",
                                        (container_id, job.id))
                        publisher.upload(container_id, stream, os.fstat(stream.fileno()).st_size, job.fingerprint)
                    self.db.execute("UPDATE instagram_tests SET status = 'processing', processing_started_at = ? WHERE id = ?",
                                    (self.workflow.now().isoformat(), job.id))
                except Exception:
                    return self._save(job.id, 'blocked', '建立或上傳未確認完成；未送出正式發佈，停止重試')
                job = self.get(job.id)
            if job.status == 'processing':
                if job.next_check_at and self.workflow.now() < datetime.fromisoformat(job.next_check_at):
                    return job
                started = self.db.execute('SELECT processing_started_at FROM instagram_tests WHERE id = ?',
                                          (job.id,)).fetchone()[0]
                deadline = datetime.fromisoformat(started) + timedelta(minutes=5)
                if self.workflow.now() > deadline:
                    return self._save(job.id, 'blocked', '媒體處理超過五分鐘，未送出正式發佈')
                assert job.container_id is not None
                try:
                    status = publisher.status(job.container_id)
                except Exception:
                    return self._save(job.id, 'blocked', '無法核對媒體處理結果，未送出正式發佈')
                if self.workflow.now() > deadline:
                    return self._save(job.id, 'blocked', '媒體處理超過五分鐘，未送出正式發佈')
                if status == 'IN_PROGRESS':
                    if self.workflow.now() >= deadline:
                        return self._save(job.id, 'blocked', '媒體處理超過五分鐘，未送出正式發佈')
                    self.db.execute('UPDATE instagram_tests SET next_check_at = ? WHERE id = ?',
                                    ((self.workflow.now() + timedelta(minutes=1)).isoformat(), job.id))
                    return self.get(job.id)
                if status != 'FINISHED':
                    return self._save(job.id, 'unknown' if status == 'PUBLISHED' else 'blocked',
                                      '平台狀態需人工核對；停止正式發佈')
                self._save(job.id, 'ready')
                job = self.get(job.id)
                ready_checked = True
            if job.status == 'ready':
                if job.scheduled_for and self.workflow.now() < datetime.fromisoformat(job.scheduled_for):
                    self.db.execute('UPDATE instagram_tests SET next_check_at = ? WHERE id = ?',
                                    (job.scheduled_for, job.id))
                    return self.get(job.id)
                if not ready_checked:
                    assert job.container_id is not None
                    try:
                        status = publisher.status(job.container_id)
                    except Exception:
                        return self._save(job.id, 'blocked', '無法重新核對媒體就緒狀態，未送出正式發佈')
                    if status != 'FINISHED':
                        return self._save(job.id, 'unknown' if status == 'PUBLISHED' else 'blocked',
                                          '發佈時媒體狀態需人工核對，停止正式發佈')
                self._check(job)
                current = self.get(job.id)
                if not current.approved_at or self.workflow.now() >= self._cutoff(current):
                    return self._save(job.id, 'blocked', '已超過核准發佈時間30分鐘，需重新審核')
                assert job.container_id is not None
                self._save(job.id, 'publishing')
                try:
                    media_id = publisher.publish(job.container_id)
                except Exception:
                    return self._save(job.id, 'unknown', '正式發佈回應不明；停止重送，需人工核對 IG')
                try:
                    self.db.execute('BEGIN IMMEDIATE')
                    self.db.execute("UPDATE instagram_tests SET status = 'published', media_id = ?, next_check_at = NULL WHERE id = ?",
                                    (media_id, job.id))
                    self.db.execute("UPDATE candidates SET status = 'published' WHERE id = ?", (job.candidate_id,))
                    self.db.execute('COMMIT')
                except BaseException:
                    if self.db.in_transaction:
                        self.db.execute('ROLLBACK')
                    raise
                try:
                    link = publisher.permalink(media_id)
                    self.db.execute('UPDATE instagram_tests SET permalink = ? WHERE id = ?', (link, job.id))
                except Exception:
                    pass  # The saved media ID is already a success receipt; never publish again.
            return self.get(job.id)
