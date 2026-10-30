"""Undeployed lifecycle prototype: local copies and a simulated platform only.

There is deliberately no network adapter, token handling, scheduler installation,
production CLI, or claim that this proves cloud execution while a Mac is off.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import TracebackType
from typing import Literal, Protocol
from zoneinfo import ZoneInfo
import fcntl
import hashlib
import json
import os
import sqlite3

from .releases import ApprovedRelease


@dataclass(frozen=True)
class PrototypeJob:
    id: str
    status: str
    release: ApprovedRelease
    media_id: str | None
    succeeded_at: str | None
    simulated: bool = True


class NotPublished(Exception):
    """Test-only proof that no formal publish happened; never inferred from timeout."""

    def __init__(self, reason: Literal['temporary', 'not_ready', 'authorization']) -> None:
        self.reason = reason
        super().__init__(reason)


class SimulatedPlatform:
    """External-platform test double; no real HTTP or credentials are accepted."""

    def __init__(self) -> None:
        self.published: list[str] = []

    def publish(self, job_id: str, caption: str, media: Path) -> str:
        self.published.append(job_id)
        return f'simulated-{job_id}'

    def lookup(self, job_id: str) -> str | None:
        return f'simulated-{job_id}' if job_id in self.published else None


class IncidentSink(Protocol):
    def send_incident(self, job_id: str, status: str) -> None: ...


class CloudPrototype:
    """Durable operations for exercising the approved workflow with fake services."""

    def __init__(self, directory: Path, platform: SimulatedPlatform,
                 *, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        if now().tzinfo is None:
            raise ValueError('時鐘必須包含時區')
        self.directory = directory.resolve()
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.platform = platform
        self.now = now
        self.db = sqlite3.connect(directory / 'prototype.sqlite3', isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, release TEXT NOT NULL, status TEXT NOT NULL,
            media_key TEXT NOT NULL, media_id TEXT, succeeded_at TEXT
        )''')
        self.db.execute('CREATE TABLE IF NOT EXISTS archives (job_id TEXT PRIMARY KEY, path TEXT NOT NULL, status TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS alerts (job_id TEXT PRIMARY KEY, status TEXT NOT NULL)')
        self.media = self.directory / 'simulation-media'
        self.media.mkdir(mode=0o700, exist_ok=True)

    def __enter__(self) -> 'CloudPrototype':
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        self.db.close()

    def get(self, job_id: str) -> PrototypeJob:
        row = self.db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
        if row is None:
            raise ValueError('找不到模擬工作')
        return PrototypeJob(str(row['id']), str(row['status']), ApprovedRelease(**json.loads(row['release'])),
                            row['media_id'], row['succeeded_at'])

    def jobs(self) -> list[PrototypeJob]:
        return [self.get(str(row['id'])) for row in self.db.execute('SELECT id FROM jobs ORDER BY id')]

    def upload(self, release: ApprovedRelease) -> PrototypeJob:
        from dataclasses import asdict
        if (len(release.fingerprint) != 64 or any(c not in '0123456789abcdef' for c in release.fingerprint)
                or not release.caption.strip() or release.revision < 1):
            raise ValueError('無效的核准內容')
        due = datetime.fromisoformat(release.scheduled_for)
        if due.tzinfo is None or due <= self.now():
            raise ValueError('需重新確認未來的發佈日期')
        job_id = hashlib.sha256(f'{release.candidate_id}:{release.revision}'.encode()).hexdigest()
        serialized = json.dumps(asdict(release), sort_keys=True, ensure_ascii=False)
        with self._lock():
            row = self.db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
            if row:
                if row['release'] != serialized:
                    raise ValueError('相同版本不得改變核准內容')
                if row['status'] != 'uploading':
                    return self.get(job_id)
            else:
                self.db.execute('INSERT INTO jobs (id, release, status, media_key) VALUES (?, ?, ?, ?)',
                                (job_id, serialized, 'uploading', release.fingerprint))
            data = Path(release.path).read_bytes()
            if hashlib.sha256(data).hexdigest() != release.fingerprint:
                raise ValueError('影片內容與核准版本不符')
            temporary = self.media / (release.fingerprint + '.partial')
            temporary.write_bytes(data)
            temporary.replace(self.media / release.fingerprint)
            self.db.execute("UPDATE jobs SET status = 'uploaded' WHERE id = ?", (job_id,))
            return self.get(job_id)

    def activate(self, job_id: str) -> PrototypeJob:
        with self._lock():
            job = self.get(job_id)
            if job.status == 'active':
                return job
            if job.status != 'uploaded' or datetime.fromisoformat(job.release.scheduled_for) <= self.now():
                raise ValueError('必須完整傳送且未過期才可啟用')
            media = self.media / job.release.fingerprint
            if hashlib.sha256(media.read_bytes()).hexdigest() != job.release.fingerprint:
                raise ValueError('媒體副本驗證失敗')
            # Keep even cancelled slots reserved: cancellation never rearranges the calendar.
            for other in self.jobs():
                if (other.id != job_id and other.release.scheduled_for == job.release.scheduled_for
                        and not (other.status == 'cancelled'
                                 and other.release.candidate_id == job.release.candidate_id)):
                    raise ValueError('時段已有其他工作，請重新審核')
            self.db.execute("UPDATE jobs SET status = 'active' WHERE id = ?", (job_id,))
            return self.get(job_id)

    @contextmanager
    def _lock(self) -> Iterator[None]:
        with (self.directory / 'prototype.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def send_alerts(self, notifier: IncidentSink) -> dict[str, str]:
        with self._lock():
            self.db.execute("UPDATE alerts SET status = 'unknown' WHERE status = 'sending'")
            for job in self.jobs():
                if job.status not in ('unknown', 'authorization_required', 'expired'):
                    continue
                self.db.execute("INSERT OR IGNORE INTO alerts VALUES (?, 'pending')", (job.id,))
                row = self.db.execute('SELECT status FROM alerts WHERE job_id = ?', (job.id,)).fetchone()
                if row['status'] != 'pending':
                    continue
                self.db.execute("UPDATE alerts SET status = 'sending' WHERE job_id = ?", (job.id,))
                try:
                    notifier.send_incident(job.id, job.status)
                except Exception:
                    status = 'unknown'
                else:
                    status = 'sent'
                self.db.execute('UPDATE alerts SET status = ? WHERE job_id = ?', (status, job.id))
            return {str(row['job_id']): str(row['status']) for row in self.db.execute('SELECT * FROM alerts')}

    def cleanup(self) -> dict[str, str]:
        results: dict[str, str] = {}
        with self._lock():
            jobs = self.jobs()
            for job in jobs:
                if job.status != 'succeeded' or not job.succeeded_at:
                    continue
                due = datetime.fromisoformat(job.succeeded_at) + timedelta(days=7)
                if self.now() < due:
                    continue
                references = [other for other in jobs if other.release.fingerprint == job.release.fingerprint]
                if any(other.status != 'succeeded' or not other.succeeded_at or
                       self.now() < datetime.fromisoformat(other.succeeded_at) + timedelta(days=7)
                       for other in references):
                    results[job.id] = 'retained_shared'
                    continue
                target = self.media / job.release.fingerprint
                try:
                    if self.media.is_symlink() or target.is_symlink():
                        results[job.id] = 'unsafe_path'
                        continue
                    target.unlink(missing_ok=True)
                    results[job.id] = 'deleted'
                except OSError:
                    results[job.id] = 'cleanup_failed'
            return results

    def archive(self, job_id: str, published: Path) -> str:
        with self._lock():
            job = self.get(job_id)
            if job.status != 'succeeded' or not job.media_id:
                return 'not_published'
            source = Path(job.release.path)
            target = published / source.name
            if not published.is_dir() or target.absolute() == source.absolute():
                return 'invalid_destination'
            record = self.db.execute('SELECT * FROM archives WHERE job_id = ?', (job_id,)).fetchone()
            if record and record['path'] != str(target.absolute()):
                return 'conflict'
            try:
                if source.is_symlink() or target.is_symlink():
                    return 'conflict'
                if target.exists():
                    if not record or hashlib.sha256(target.read_bytes()).hexdigest() != job.release.fingerprint:
                        return 'conflict'
                    if source.exists():
                        if not os.path.samefile(source, target):
                            return 'conflict'
                        source.unlink()
                else:
                    if not source.is_file():
                        return 'missing_source'
                    if hashlib.sha256(source.read_bytes()).hexdigest() != job.release.fingerprint:
                        return 'content_changed'
                    self.db.execute('INSERT OR REPLACE INTO archives VALUES (?, ?, ?)',
                                    (job_id, str(target.absolute()), 'prepared'))
                    os.link(source, target)  # Atomic refusal to overwrite, including competing processes.
                    if hashlib.sha256(target.read_bytes()).hexdigest() != job.release.fingerprint:
                        return 'content_changed'
                    source.unlink()
                self.db.execute('INSERT OR REPLACE INTO archives VALUES (?, ?, ?)',
                                (job_id, str(target.absolute()), 'archived'))
                return 'archived'
            except FileExistsError:
                return 'conflict'
            except OSError:
                return 'local_error'

    def replace(self, job_id: str, release: ApprovedRelease) -> PrototypeJob:
        old = self.get(job_id)
        if release.candidate_id != old.release.candidate_id or release.revision <= old.release.revision:
            raise ValueError('修改需要相同候選的新核准版本')
        if self.cancel(job_id).status != 'cancelled':
            raise ValueError('原版本已進入發佈或待核對，不能宣稱修改成功')
        # A failed replacement leaves the old version cancelled, never silently reactivated.
        return self.upload(release)

    def cancel(self, job_id: str) -> PrototypeJob:
        with self._lock():
            job = self.get(job_id)
            if job.status in ('uploading', 'uploaded', 'active', 'retry_wait'):
                self.db.execute("UPDATE jobs SET status = 'cancelled' WHERE id = ?", (job.id,))
            # The returned state is the confirmed outcome, including a lost cancel race.
            return self.get(job_id)

    def reconcile(self, job_id: str) -> PrototypeJob:
        with self._lock():
            job = self.get(job_id)
            if job.status not in ('unknown', 'publishing'):
                return job
            try:
                receipt = self.platform.lookup(job.id)
            except Exception:
                receipt = None
            if receipt:
                # Conservatively start retention at confirmation, never earlier than success.
                self.db.execute("UPDATE jobs SET status = 'succeeded', media_id = ?, succeeded_at = ? WHERE id = ?",
                                (receipt, self.now().isoformat(), job.id))
            else:
                self.db.execute("UPDATE jobs SET status = 'unknown' WHERE id = ?", (job.id,))
            return self.get(job_id)

    def run(self) -> list[PrototypeJob]:
        with self._lock():
            # A process can die after the platform publishes but before the receipt is saved.
            self.db.execute("UPDATE jobs SET status = 'unknown' WHERE status = 'publishing'")
            for job in self.jobs():
                if job.status not in ('active', 'retry_wait') or datetime.fromisoformat(job.release.scheduled_for) > self.now():
                    continue
                cutoff = datetime.fromisoformat(job.release.scheduled_for).astimezone(
                    ZoneInfo('Asia/Taipei')).replace(hour=20, minute=30, second=0, microsecond=0)
                if self.now() >= cutoff:
                    self.db.execute("UPDATE jobs SET status = 'expired' WHERE id = ?", (job.id,))
                    continue
                self.db.execute("UPDATE jobs SET status = 'publishing' WHERE id = ?", (job.id,))
                try:
                    receipt = self.platform.publish(job.id, job.release.caption, self.media / job.release.fingerprint)
                except NotPublished as error:
                    status = 'authorization_required' if error.reason == 'authorization' else 'retry_wait'
                    self.db.execute('UPDATE jobs SET status = ? WHERE id = ?', (status, job.id))
                except Exception:
                    self.db.execute("UPDATE jobs SET status = 'unknown' WHERE id = ?", (job.id,))
                else:
                    if not receipt:
                        self.db.execute("UPDATE jobs SET status = 'unknown' WHERE id = ?", (job.id,))
                    else:
                        self.db.execute("UPDATE jobs SET status = 'succeeded', media_id = ?, succeeded_at = ? WHERE id = ?",
                                        (receipt, self.now().isoformat(), job.id))
            return self.jobs()
