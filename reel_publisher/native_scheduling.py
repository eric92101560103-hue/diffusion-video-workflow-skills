"""Durable intent and observed receipts for Meta UI operations; never sends a post."""
from contextlib import contextmanager
from collections.abc import Iterator
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import TYPE_CHECKING
import json
import uuid
import os
import shutil

if TYPE_CHECKING:
    from .workflow import Workflow


@dataclass(frozen=True)
class NativeJob:
    id: str
    candidate_id: str
    source_path: str
    source_fingerprint: str
    media_path: str
    media_fingerprint: str
    caption: str
    scheduled_for: str
    status: str = 'prepared'
    revision: int = 1
    account_id: str = '17841403997461963'
    username: str = '_eric_han'
    native_schedule_id: str | None = None
    operation_id: str | None = None
    operation: str | None = None
    proposed_caption: str | None = None
    proposed_for: str | None = None
    media_id: str | None = None
    permalink: str | None = None
    published_at: str | None = None
    checked_at: str | None = None
    archived_path: str | None = None
    operation_started_at: str | None = None
    approval_revision: int = 0
    recovery_path: str | None = None
    check_problem: str | None = None
    check_problem_at: str | None = None


@dataclass(frozen=True)
class NativeObservation:
    receipt_id: str
    result: str
    account_id: str
    username: str
    caption: str
    scheduled_for: str
    media_fingerprint: str
    checked_at: str
    source_url: str
    evidence_path: str
    operation_id: str | None = None
    native_schedule_id: str | None = None
    reloaded: bool = False
    upload_complete: bool = False
    public: bool = False
    instagram_only: bool = False
    cancellation_confirmed: bool = False
    operation_not_applied: bool = False
    media_id: str | None = None
    permalink: str | None = None
    published_at: str | None = None


    def __post_init__(self) -> None:
        from .workflow import WorkflowError
        boolean_fields = {'reloaded', 'upload_complete', 'public', 'instagram_only', 'cancellation_confirmed', 'operation_not_applied'}
        optional_fields = {'operation_id', 'native_schedule_id', 'media_id', 'permalink', 'published_at'}
        for key, value in asdict(self).items():
            if key in boolean_fields:
                valid = type(value) is bool
            elif key in optional_fields:
                valid = value is None or isinstance(value, str)
            else:
                valid = isinstance(value, str) and bool(value.strip())
            if not valid:
                raise WorkflowError('回執欄位型別或必要內容無效')


class NativeSchedules:
    def __init__(self, workflow: 'Workflow') -> None:
        self.workflow = workflow
        self.db = workflow.db

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def get(self, job_id: str) -> NativeJob:
        from .workflow import WorkflowError
        row = self.db.execute('SELECT payload FROM native_jobs WHERE id = ?', (job_id,)).fetchone()
        if not row:
            raise WorkflowError('找不到原生排程紀錄')
        return NativeJob(**json.loads(row['payload']))

    def jobs(self) -> list[NativeJob]:
        return [NativeJob(**json.loads(row['payload'])) for row in self.db.execute(
            'SELECT payload FROM native_jobs ORDER BY rowid')]

    def save(self, job: NativeJob) -> NativeJob:
        self.db.execute('UPDATE native_jobs SET payload = ?, native_schedule_id = ? WHERE id = ?',
                        (json.dumps(asdict(job), ensure_ascii=False), job.native_schedule_id, job.id))
        return job

    def prepare(self, candidate_id: str, revision: int, media: Path | None) -> NativeJob:
        from .workflow import WorkflowError, fingerprint
        with self.transaction():
            candidate = self.workflow.get(candidate_id)
            if candidate.revision != revision:
                raise WorkflowError('候選版本已改變，請重新查看')
            release = self.workflow._native_release(candidate_id)
            # A transformed upload must be explicitly reviewed by caller, not silently substituted.
            path = media or Path(release.path)
            if path.is_symlink() or not path.is_file():
                raise WorkflowError('上傳檔必須是一般檔案')
            self.workflow.inspect_media(path)
            identifier = uuid.uuid4().hex
            directory = self.workflow.config.database.parent / (self.workflow.config.database.name + '.native-media')
            if directory.is_symlink():
                raise WorkflowError('私有上傳目錄不能是連結')
            directory.mkdir(mode=0o700, exist_ok=True)
            private = directory / identifier
            private.mkdir(mode=0o700)
            upload = private / 'upload.mp4'
            digest = fingerprint(path)
            with upload.open('xb') as output, path.open('rb') as input_file:
                os.chmod(upload, 0o600)
                shutil.copyfileobj(input_file, output)
                output.flush()
                os.fsync(output.fileno())
            if (fingerprint(upload) != digest or fingerprint(path) != digest
                    or fingerprint(Path(release.path)) != release.fingerprint):
                raise WorkflowError('上傳副本不完整或來源變動，停止交付')
            job = NativeJob(identifier, candidate_id, release.path, release.fingerprint,
                            str(upload.resolve()), digest, release.caption, release.scheduled_for, approval_revision=revision)
            self.db.execute('INSERT INTO native_jobs (id, candidate_id, payload) VALUES (?, ?, ?)',
                            (job.id, candidate_id, json.dumps(asdict(job), ensure_ascii=False)))
            self.db.execute("UPDATE candidates SET status = 'native_pending' WHERE id = ?", (candidate_id,))
            return job

    def withdraw(self, job_id: str, confirmed: bool) -> NativeJob:
        from .workflow import WorkflowError
        with self.transaction():
            job = self.get(job_id)
            if not confirmed or job.status != 'prepared' or job.operation_id or job.native_schedule_id:
                raise WorkflowError('只有尚未開始外部操作的本機準備可撤回；未知結果先核對 Meta')
            self.db.execute("UPDATE candidates SET status = 'cancelled', approval_revision = NULL WHERE id = ?",
                            (job.candidate_id,))
            return self.save(replace(job, status='withdrawn', revision=job.revision + 1))

    def begin(self, job_id: str, revision: int, action: str, confirmed: bool,
              caption: str | None, scheduled_for: datetime | None) -> NativeJob:
        from .workflow import WorkflowError, fingerprint
        with self.transaction():
            job = self.get(job_id)
            if not confirmed or job.revision != revision:
                raise WorkflowError('需確認目前原生排程版本及確切操作')
            if job.check_problem:
                raise WorkflowError('平台核對仍有阻擋，先恢復並核對最新結果')
            if job.operation_id or action not in ('create', 'modify', 'cancel'):
                raise WorkflowError('操作結果不明或動作無效；先核對 Meta，禁止重送')
            if (action == 'create' and job.status != 'prepared') or (
                    action != 'create' and job.status != 'scheduled'):
                raise WorkflowError('目前平台狀態不允許此操作')
            when = scheduled_for.isoformat() if scheduled_for else job.scheduled_for
            text = caption if caption is not None else job.caption
            if action != 'modify' and (caption is not None or scheduled_for is not None):
                raise WorkflowError('只有修改操作能更換文案或日期')
            if action != 'cancel':
                moment = datetime.fromisoformat(when)
                if moment.tzinfo is None or moment <= self.workflow.now() or not text.strip():
                    raise WorkflowError('文案或未來發佈時間無效')
                local = moment.astimezone(ZoneInfo('Asia/Taipei'))
                if (local.hour, local.minute, local.second, local.microsecond) != (20, 0, 0, 0):
                    raise WorkflowError('發佈時刻必須是台北時間20:00')
                if moment in self.workflow._reserved_slots([job.candidate_id]):
                    raise WorkflowError('此時段已有其他影片或待核對操作；不改動其他日期')
                anchor = self.db.execute("SELECT value FROM settings WHERE name = 'first_date'").fetchone()
                if anchor:
                    from datetime import date
                    if (local.date() - date.fromisoformat(str(anchor['value']))).days % 2:
                        raise WorkflowError('日期必須沿用首發日的隔日節奏')
            if action == 'create':
                candidate = self.workflow.get(job.candidate_id)
                if (candidate.status != 'native_pending' or candidate.revision != job.approval_revision
                        or candidate.caption != job.caption or candidate.scheduled_for != job.scheduled_for):
                    raise WorkflowError('原核准快照已改變；停止交付')
                self.workflow._check_video(candidate)
                if fingerprint(Path(job.media_path)) != job.media_fingerprint:
                    raise WorkflowError('上傳檔已變更；停止交付')
            pending = replace(job, status='unknown', revision=job.revision + 1,
                              operation_id=uuid.uuid4().hex, operation=action,
                              proposed_caption=text, proposed_for=when, operation_started_at=self.workflow.now().isoformat())
            self.db.execute("UPDATE candidates SET status = 'native_unknown' WHERE id = ?", (job.candidate_id,))
            return self.save(pending)

    def observe(self, job_id: str, observation: NativeObservation) -> NativeJob:
        from .workflow import WorkflowError, fingerprint
        proof = Path(observation.evidence_path)
        if proof.is_symlink() or not proof.is_file():
            raise WorkflowError('需要可讀取的一般證據檔案')
        payload = json.dumps({'observation': asdict(observation), 'proof_fingerprint': fingerprint(proof)},
                             ensure_ascii=False, sort_keys=True)
        with self.transaction():
            job = self.get(job_id)
            previous = self.db.execute('SELECT job_id, payload FROM native_receipts WHERE id = ?',
                                       (observation.receipt_id,)).fetchone()
            if previous:
                if previous['job_id'] != job.id or previous['payload'] != payload:
                    raise WorkflowError('回執識別已被其他內容使用')
                return job
            checked = datetime.fromisoformat(observation.checked_at)
            host = urlparse(observation.source_url)
            if (not observation.receipt_id.strip() or checked.tzinfo is None
                    or checked > self.workflow.now() or (job.checked_at and checked < datetime.fromisoformat(job.checked_at))
                    or (job.operation_started_at and checked < datetime.fromisoformat(job.operation_started_at))
                    or (job.check_problem_at and checked < datetime.fromisoformat(job.check_problem_at))
                    or not observation.reloaded or host.scheme != 'https'
                    or host.hostname != 'business.facebook.com' or host.username or host.password
                    or not host.path.startswith('/latest/') or host.fragment
                    or set(parse_qs(host.query)) - {'asset_id', 'business_id', 'post_id'}
                    or (observation.account_id, observation.username) != (job.account_id, job.username)
                    or observation.media_fingerprint != job.media_fingerprint):
                raise WorkflowError('回執帳號、檔案、時間或重新載入證據不符')
            if observation.operation_id != job.operation_id:
                raise WorkflowError('回執不屬於目前操作；先查看最新紀錄')
            schedule_id = observation.native_schedule_id
            if job.native_schedule_id and schedule_id != job.native_schedule_id:
                raise WorkflowError('回執不是同一筆 Meta 排程')
            result = observation.result
            if job.status == 'withdrawn' or (job.status in ('published', 'cancelled') and result != job.status):
                raise WorkflowError('正式結果不可被舊排程或不明回執覆蓋')
            if result not in ('scheduled', 'published', 'cancelled', 'unknown', 'failed'):
                raise WorkflowError('不支援的核對結果')
            text = job.proposed_caption if job.proposed_caption is not None else job.caption
            when = job.proposed_for or job.scheduled_for
            # The old version can publish while a modification is being attempted.
            if (result == 'published' and job.native_schedule_id and job.operation == 'modify'
                    and observation.caption == job.caption
                    and datetime.fromisoformat(observation.scheduled_for) == datetime.fromisoformat(job.scheduled_for)):
                text, when = job.caption, job.scheduled_for
            if observation.operation_not_applied:
                if (result != 'scheduled' or job.operation not in ('modify', 'cancel')
                        or not job.native_schedule_id):
                    raise WorkflowError('只有核實未套用的修改／取消，才可恢復既有排程')
                text, when = job.caption, job.scheduled_for
            if result in ('scheduled', 'published'):
                if (not schedule_id or not observation.public or not observation.instagram_only
                        or observation.caption != text
                        or datetime.fromisoformat(observation.scheduled_for) != datetime.fromisoformat(when)
                        or not observation.upload_complete):
                    raise WorkflowError('保存的文案、時間、可見性或上傳狀態不符')
                if result == 'scheduled' and job.operation == 'cancel' and not observation.operation_not_applied:
                    raise WorkflowError('取消尚未確認；保留待核對')
            if result == 'cancelled' and (job.operation != 'cancel' or not observation.cancellation_confirmed):
                raise WorkflowError('清單缺席不能證明取消；需要明確取消結果')
            media_id, permalink, published_at = job.media_id, job.permalink, job.published_at
            if result == 'published':
                link = urlparse(observation.permalink or '')
                at = datetime.fromisoformat(observation.published_at or '')
                if (at.tzinfo is None or at > checked or not observation.media_id
                        or observation.media_id == schedule_id or link.scheme != 'https'
                        or link.hostname not in ('www.instagram.com', 'instagram.com')
                        or link.username or link.password or not link.path.startswith(('/reel/', '/p/'))):
                    raise WorkflowError('正式發佈需要獨立媒體 ID、IG 貼文連結及正確時間')
                if job.status == 'published' and (
                        observation.media_id, observation.permalink, observation.published_at) != (
                        job.media_id, job.permalink, job.published_at):
                    raise WorkflowError('正式發佈識別與時間已固定；衝突回執需人工核對')
                media_id, permalink, published_at = observation.media_id, observation.permalink, observation.published_at
            resolved = result in ('scheduled', 'published', 'cancelled')
            saved = replace(job, status=result, revision=job.revision + 1,
                            native_schedule_id=schedule_id or job.native_schedule_id,
                            caption=text if resolved else job.caption, scheduled_for=when if resolved else job.scheduled_for,
                            operation_id=None if resolved else job.operation_id,
                            operation=None if resolved else job.operation,
                            proposed_caption=None if resolved else job.proposed_caption,
                            proposed_for=None if resolved else job.proposed_for,
                            media_id=media_id, permalink=permalink, published_at=published_at,
                            checked_at=observation.checked_at,
                            operation_started_at=None if resolved else job.operation_started_at,
                            check_problem=None, check_problem_at=None)
            state = {'scheduled': 'native_scheduled', 'cancelled': 'cancelled', 'published': 'published'}.get(result, 'native_unknown')
            self.db.execute('UPDATE candidates SET status = ?, caption = ?, scheduled_for = ? WHERE id = ?',
                            (state, saved.caption, saved.scheduled_for, job.candidate_id))
            self.db.execute('INSERT INTO native_receipts VALUES (?, ?, ?)', (observation.receipt_id, job.id, payload))
            return self.save(saved)

    def archive(self, job_id: str) -> NativeJob:
        from .workflow import WorkflowError, fingerprint
        import fcntl
        import os
        import shutil
        with self.workflow.config.database.with_suffix('.native-archive.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            job = self.get(job_id)
            if job.status != 'published' or not job.media_id or not job.permalink:
                raise WorkflowError('只有已核實正式成功的原片才能歸檔')
            source = Path(job.source_path)
            destination = self.workflow.config.published.resolve() / source.name
            if job.archived_path:
                if destination.is_symlink() or not destination.is_file() or fingerprint(destination) != job.source_fingerprint:
                    raise WorkflowError('已歸檔成片已變動，請人工整理；不重新發佈')
                return job
            if not destination.parent.is_dir() or destination.parent == source.parent:
                raise WorkflowError('歸檔資料夾不可用')
            row = self.db.execute('SELECT * FROM native_archives WHERE job_id = ?', (job.id,)).fetchone()
            if not row:
                if destination.exists() or destination.is_symlink():
                    raise WorkflowError('歸檔同名衝突；保留原片與既有成片')
                if source.is_symlink() or not source.is_file() or fingerprint(source) != job.source_fingerprint:
                    raise WorkflowError('原片缺少、移動或內容已改變，請人工整理')
                stage = destination.parent / ('.reels-' + uuid.uuid4().hex + '.partial')
                quarantine_dir = source.parent / ('.reels-source-' + uuid.uuid4().hex)
                quarantine_dir.mkdir(mode=0o700)
                quarantine = quarantine_dir / 'original'
                self.db.execute('INSERT INTO native_archives VALUES (?, ?, ?, ?)',
                                (job.id, str(destination), str(stage), str(quarantine)))
            else:
                if row['destination'] != str(destination):
                    raise WorkflowError('歸檔路徑已變動；請使用原配置恢復')
                stage = Path(row['stage'])
                quarantine = Path(row['quarantine'])
            if stage.is_symlink() or destination.is_symlink():
                raise WorkflowError('歸檔路徑不能是連結')
            if not stage.exists() or fingerprint(stage) != job.source_fingerprint:
                if destination.exists():
                    raise WorkflowError('歸檔結果需要人工核對；不覆寫既有檔案')
                if source.is_symlink() or fingerprint(source) != job.source_fingerprint:
                    raise WorkflowError('原片內容不符；不歸檔')
                exists = stage.exists()
                flags = os.O_WRONLY | os.O_NOFOLLOW
                if not exists:
                    flags |= os.O_CREAT | os.O_EXCL
                descriptor = os.open(stage, flags, 0o600)
                with os.fdopen(descriptor, 'wb') as output, source.open('rb') as input_file:
                    import stat
                    metadata = os.fstat(output.fileno())
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                        raise WorkflowError('受控暫存身分異常；不改寫既有檔案')
                    os.ftruncate(output.fileno(), 0)
                    shutil.copyfileobj(input_file, output)
                    output.flush()
                    os.fsync(output.fileno())
                if fingerprint(stage) != job.source_fingerprint:
                    raise WorkflowError('歸檔暫存不完整；保留原片，稍後重跑')
            if not destination.exists():
                # Hard-link is atomic and never replaces another film, including across retries.
                os.link(stage, destination)
            if not os.path.samefile(stage, destination):
                raise WorkflowError('歸檔同名衝突；不刪除原片或覆寫成片')
            if quarantine.parent.is_symlink() or quarantine.is_symlink():
                raise WorkflowError('受控原片交接路徑異常；保留檔案')
            if not quarantine.exists() and (source.exists() or source.is_symlink()):
                if source.is_symlink() or fingerprint(source) != job.source_fingerprint:
                    raise WorkflowError('原片內容已變更；保留兩份並等待人工整理')
                # Rename first: a concurrent replacement is captured and checked, never unlinked at its public path.
                os.rename(source, quarantine)
            if quarantine.exists() and fingerprint(quarantine) != job.source_fingerprint:
                if not source.exists() and not source.is_symlink():
                    os.link(quarantine, source)  # Restore without overwriting a newer source.
                    quarantine.unlink()
                raise WorkflowError('交接期間原片已變更，已保留新檔；請人工整理')
            with self.transaction():
                self.save(replace(self.get(job.id), recovery_path=str(quarantine) if quarantine.exists() else None))
            if (destination.is_symlink() or not os.path.samefile(stage, destination)
                    or fingerprint(destination) != job.source_fingerprint):
                raise WorkflowError('歸檔目的檔在交接期間變動；原片已保存在 recovery_path，等待人工整理')
            with self.transaction():
                result = self.save(replace(self.get(job.id), archived_path=str(destination)))
            # Keep the captured original: an unrelated editor can change the public destination even after verification.
            stage.unlink()
            return result

    def blocked(self, job_id: str, reason: str) -> NativeJob:
        from .workflow import WorkflowError
        if reason not in ('browser_unavailable', 'login_required', 'item_mismatch'):
            raise WorkflowError('請使用已定義的核對阻擋類型；不保存原始登入或錯誤內容')
        with self.transaction():
            job = self.get(job_id)
            if job.status in ('prepared', 'withdrawn', 'cancelled') or job.archived_path:
                raise WorkflowError('此項目已結束，不需要新增平台核對阻擋')
            checked_at = self.workflow.now().isoformat()
            if job.check_problem == reason:
                return self.save(replace(job, check_problem_at=checked_at))
            return self.save(replace(job, check_problem=reason, check_problem_at=checked_at, revision=job.revision + 1))

    def check(self) -> list[dict[str, str]]:
        from .chat_notifications import ChatItem
        items = []
        with self.transaction():
            for job in self.jobs():
                reason = None
                if job.check_problem:
                    reason = job.check_problem
                elif job.status in ('unknown', 'failed'):
                    reason = 'unknown' if job.status == 'unknown' else 'failed'
                elif (job.status == 'scheduled' and self.workflow.now() >=
                      datetime.fromisoformat(job.scheduled_for) + timedelta(minutes=30)):
                    reason = 'overdue_unverified'
                elif job.status == 'published' and not job.archived_path:
                    reason = 'archive_pending'
                row = self.db.execute('SELECT reason, event_key FROM native_faults WHERE job_id = ?', (job.id,)).fetchone()
                if row and row['reason'] != reason:
                    self.db.execute("UPDATE chat_events SET status = 'obsolete' WHERE event_key = ? AND status = 'pending'", (row['event_key'],))
                    if reason is None and job.status in ('scheduled', 'published', 'cancelled'):
                        recovery = ChatItem('native_recovery', job.id, 'Meta 狀態已核對：' + job.status)
                        self.db.execute('INSERT OR IGNORE INTO chat_events VALUES (?, ?, ?, NULL)',
                            ('native-recovery:' + str(row['event_key']), json.dumps(asdict(recovery), ensure_ascii=False), 'pending'))
                    self.db.execute('DELETE FROM native_faults WHERE job_id = ?', (job.id,))
                    row = None
                if reason is None:
                    continue
                key = str(row['event_key']) if row else 'native:' + job.id + ':' + uuid.uuid4().hex
                if row is None:
                    self.db.execute('INSERT INTO native_faults VALUES (?, ?, ?)', (job.id, reason, key))
                item = ChatItem('native_attention', job.id,
                                {'browser_unavailable': 'Meta 瀏覽器不可用；保留最後已知平台結果，需要恢復連線後核對',
                                 'login_required': '需要重新登入 Meta 才能核對；未變更排程或重新發文',
                                 'item_mismatch': 'Meta 項目與核准內容不符；先人工核對，禁止重建或補發',
                                 'unknown': 'Meta 操作結果不明；先核對原排程，禁止 API 補發',
                                 'failed': 'Meta 回報失敗；需要人工介入，未自動重送',
                                 'overdue_unverified': '已超過20:30仍無正式成功證據；請核對 Meta，不能推定未發佈',
                                 'archive_pending': '正式發佈已核實，原片等待歸檔'}[reason])
                self.db.execute('INSERT OR IGNORE INTO chat_events VALUES (?, ?, ?, NULL)',
                                (key, json.dumps(asdict(item), ensure_ascii=False), 'pending'))
                items.append({'job_id': job.id, 'reason': reason})
        return items

    def cleanup(self, job_id: str, confirmed: bool) -> NativeJob:
        from .workflow import WorkflowError, fingerprint
        with self.transaction():
            job = self.get(job_id)
            if not confirmed or not (job.status in ('cancelled', 'withdrawn') or (job.status == 'published' and job.archived_path)):
                raise WorkflowError('只可明確清理已確認取消或成功歸檔的本機上傳副本')
            expected = self.workflow.config.database.parent / (self.workflow.config.database.name + '.native-media') / job.id / 'upload.mp4'
            path = Path(job.media_path)
            if path != expected.resolve() or expected.parent.is_symlink() or expected.parent.parent.is_symlink() or path.is_symlink():
                raise WorkflowError('此檔案不屬於工具管理的上傳副本；保留原片及證據')
            if path.exists():
                if fingerprint(path) != job.media_fingerprint:
                    raise WorkflowError('上傳副本已變動，保留並人工核對')
                path.unlink()
            return job
