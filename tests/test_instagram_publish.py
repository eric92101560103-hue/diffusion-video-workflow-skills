"""Manual publishing through the shared Workflow, with only Meta HTTP replaced."""
from io import BytesIO
import json
from unittest.mock import patch

from reel_publisher.instagram import InstagramConnection
from tests.support import WorkflowFixture

IG = '17841403997461963'
PAGE = '1424349244092893'


class Reply(BytesIO):
    status = 200

    def __init__(self, value):
        super().__init__(json.dumps(value).encode())


class Meta:
    def __init__(self):
        self.posts = []
        self.uploaded = bytearray()
        self.ready = 'FINISHED'
        self.publish_error = None
        self.on_status = None

    def open(self, request, timeout):
        if 'access_token' in request.full_url:
            return Reply({'id': PAGE, 'instagram_business_account': {'id': IG},
                          'access_token': 'synthetic-page-secret'})
        return Reply({'id': IG, 'username': '_eric_han'})

    def connection(self, host, timeout):
        meta = self

        class HTTP:
            def request(self, method, path, body=None, headers=None):
                self.method, self.path = method, path
                if method == 'POST':
                    meta.posts.append((host, path, json.loads(body)))
            def putrequest(self, method, path):
                self.method, self.path = method, path
            def putheader(self, *args):
                pass
            def endheaders(self):
                pass
            def send(self, data):
                meta.uploaded.extend(data)
            def getresponse(self):
                if host == 'rupload.facebook.com':
                    return Reply({'success': True})
                if self.method == 'POST' and self.path.endswith('/media_publish'):
                    if meta.publish_error:
                        raise meta.publish_error
                    return Reply({'id': '888000'})
                if self.method == 'POST':
                    return Reply({'id': '999000'})
                if 'status_code' in self.path:
                    if meta.on_status:
                        meta.on_status()
                    return Reply({'status_code': meta.ready})
                return Reply({'id': '888000', 'permalink': 'https://www.instagram.com/reel/test123/'})
            def close(self):
                pass
        return HTTP()


class InstagramPublishTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        self.meta = Meta()
        self.enterContext(patch('reel_publisher.instagram.build_opener', return_value=self.meta))
        self.enterContext(patch('http.client.HTTPSConnection', side_effect=self.meta.connection))
        import subprocess
        self.probe = {'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 1080, 'height': 1920,
                                  'avg_frame_rate': '30/1', 'pix_fmt': 'yuv420p', 'field_order': 'progressive',
                                  'bit_rate': '8000000'}],
                      'format': {'duration': '10', 'format_name': 'mov,mp4,m4a,3gp,3g2,mj2'}}
        self.enterContext(patch('subprocess.run', side_effect=lambda *a, **k:
                               subprocess.CompletedProcess(a[0], 0, json.dumps(self.probe), '')))

    def publisher(self):
        from reel_publisher.instagram_publishing import FacebookReels
        return FacebookReels(InstagramConnection(IG, 'v26.0', 'synthetic-user-secret', 'facebook'), PAGE)

    def prepared(self, workflow):
        self.video()
        item = workflow.scan().discovered[0]
        item = workflow.set_caption(item.id, '人工核准的測試文案')
        return workflow.instagram_test_prepare(item.id, item.revision, page_id=PAGE, version='v26.0')

    def test_explicit_manual_test_publishes_reviewed_bytes_and_saves_receipt(self):
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            self.assertEqual(job.status, 'awaiting_approval')
            self.assertEqual(self.meta.posts, [])
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual((result.status, result.media_id, result.permalink),
                             ('published', '888000', 'https://www.instagram.com/reel/test123/'))
            self.assertEqual(bytes(self.meta.uploaded), b'completed video')
            self.assertEqual(workflow.get(job.candidate_id).status, 'published')
        with self.workflow() as workflow:
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.media_id, '888000')
            self.assertEqual(sum(path.endswith('/media_publish') for _, path, _ in self.meta.posts), 1)

    def test_processing_waits_a_minute_then_publishes_only_once(self):
        from datetime import timedelta
        self.meta.ready = 'IN_PROGRESS'
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'processing')
            self.assertEqual(result.next_check_at, '2026-11-01T02:01:00+00:00')
            self.assertEqual(sum(p.endswith('/media_publish') for _, p, _ in self.meta.posts), 0)
            self.meta.ready = 'FINISHED'
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'processing')
            self.now += timedelta(minutes=1)
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'published')

    def test_lost_publish_reply_is_unknown_across_restarts_without_a_second_post(self):
        self.meta.publish_error = TimeoutError('synthetic-page-secret provider URL')
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'unknown')
            self.assertNotIn('synthetic', result.reason)
            self.assertNotEqual(workflow.get(job.candidate_id).status, 'published')
        with self.workflow() as workflow:
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'unknown')
            self.assertIsNone(result.media_id)
            self.assertEqual(sum(p.endswith('/media_publish') for _, p, _ in self.meta.posts), 1)

    def test_cancel_processing_stops_publish_and_requires_a_new_review_revision(self):
        self.meta.ready = 'IN_PROGRESS'
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            result = workflow.instagram_test_cancel(job.id, confirmed=True)
            self.assertEqual(result.status, 'cancelled')
            item = workflow.get(job.candidate_id)
            self.assertEqual((item.status, item.revision), ('candidate', job.revision + 1))
            self.meta.ready = 'FINISHED'
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'cancelled')
            self.assertEqual(sum(p.endswith('/media_publish') for _, p, _ in self.meta.posts), 0)

    def test_cli_can_review_test_and_requires_explicit_publish_flag(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from reel_publisher.cli import main
        with self.workflow() as workflow:
            job = self.prepared(workflow)
        prefix = ['--database', str(self.config.database), '--source', str(self.source),
                  '--published', str(self.archive)]
        output = StringIO()
        with redirect_stdout(output):
            code = main(prefix + ['instagram-test-get', job.id])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['caption'], '人工核准的測試文案')
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            main(prefix + ['instagram-test-publish', job.id])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.meta.posts, [])

    def test_non_reels_frame_rate_is_rejected_before_preparing_or_uploading(self):
        self.probe['streams'][0]['avg_frame_rate'] = '1/1'
        with self.workflow() as workflow:
            with self.assertRaisesRegex(ValueError, '23.*60'):
                self.prepared(workflow)
        self.assertEqual(self.meta.posts, [])

    def test_approval_deadline_is_rechecked_after_a_slow_status_response(self):
        from datetime import timedelta
        self.meta.on_status = lambda: setattr(self, 'now', self.now + timedelta(minutes=31))
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'blocked')
            self.assertEqual(sum(p.endswith('/media_publish') for _, p, _ in self.meta.posts), 0)

    def test_audio_above_conservative_publishing_limit_needs_a_new_export(self):
        self.probe['streams'].append({'codec_type': 'audio', 'codec_name': 'aac', 'sample_rate': '48000',
                                      'channels': 2, 'bit_rate': '251739'})
        with self.workflow() as workflow:
            with self.assertRaisesRegex(ValueError, '128'):
                self.prepared(workflow)
        self.assertEqual(self.meta.posts, [])

    def test_corrupt_local_snapshot_is_not_uploaded_to_meta(self):
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            copies = list(self.root.rglob('*.media'))
            self.assertEqual(len(copies), 1)
            copies[0].write_bytes(b'unreviewed different content')
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'blocked')
            self.assertEqual(bytes(self.meta.uploaded), b'')

    def test_without_confirmation_or_after_caption_change_nothing_is_posted(self):
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            with self.assertRaisesRegex(ValueError, '明確核准'):
                workflow.instagram_test_publish(job.id, self.publisher())
            workflow.set_caption(job.candidate_id, '尚未核准的新文案')
            with self.assertRaisesRegex(ValueError, '版本已變更'):
                workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(self.meta.posts, [])

    def test_interrupted_formal_publish_cannot_be_cancelled_or_repeated(self):
        self.meta.publish_error = KeyboardInterrupt()
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            with self.assertRaises(KeyboardInterrupt):
                workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
        with self.workflow() as workflow:
            self.assertEqual(workflow.instagram_test_get(job.id).status, 'publishing')
            self.assertEqual(workflow.instagram_test_cancel(job.id, confirmed=True).status, 'publishing')
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'unknown')
            self.assertEqual(sum(p.endswith('/media_publish') for _, p, _ in self.meta.posts), 1)

    def test_cancel_before_first_upload_allows_a_fresh_review(self):
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            workflow.instagram_test_cancel(job.id, confirmed=True)
            candidate = workflow.get(job.candidate_id)
            revised = workflow.instagram_test_prepare(candidate.id, candidate.revision, page_id=PAGE, version='v26.0')
            self.assertNotEqual(revised.id, job.id)
            self.assertEqual(revised.status, 'awaiting_approval')

    def test_cli_uses_configured_secret_and_outputs_a_safe_receipt(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from reel_publisher.cli import main
        with self.workflow() as workflow:
            job = self.prepared(workflow)
        prefix = ['--database', str(self.config.database), '--source', str(self.source),
                  '--published', str(self.archive)]
        environment = {'REEL_IG_LOGIN': 'facebook', 'REEL_IG_ACCOUNT_ID': IG,
                       'REEL_IG_API_VERSION': 'v26.0', 'REEL_IG_ACCESS_TOKEN': 'synthetic-user-secret'}
        output = StringIO()
        with patch.dict('os.environ', environment, clear=True), redirect_stdout(output):
            code = main(prefix + ['instagram-test-publish', job.id, '--confirm-publish-now'])
        self.assertEqual(code, 0)
        receipt = json.loads(output.getvalue())
        self.assertEqual((receipt['status'], receipt['media_id']), ('published', '888000'))
        self.assertNotIn('synthetic-', output.getvalue())
        sent = [body for _, path, body in self.meta.posts if path.endswith('/media')]
        self.assertEqual(sent, [{'media_type': 'REELS', 'upload_type': 'resumable', 'caption': '人工核准的測試文案'}])

    def test_caption_write_started_before_publish_reservation_cannot_replace_approved_content(self):
        import sqlite3
        from reel_publisher import WorkflowError
        original_connect = sqlite3.connect
        before_update = None

        class ControlledDatabase(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                # Real SQLite; control only the timing at the external write boundary.
                nonlocal before_update
                if sql.startswith('UPDATE candidates SET caption') and before_update:
                    action, before_update = before_update, None
                    action()
                return super().execute(sql, parameters)

        def connect(*args, **kwargs):
            return original_connect(*args, factory=ControlledDatabase, **kwargs)

        with patch('sqlite3.connect', side_effect=connect):
            with self.workflow() as writer:
                job = self.prepared(writer)
                self.meta.ready = 'IN_PROGRESS'
                with self.workflow() as publisher:
                    before_update = lambda: publisher.instagram_test_publish(job.id, self.publisher(), confirmed=True)
                    with self.assertRaises(WorkflowError):
                        writer.set_caption(job.candidate_id, '競爭寫入的新文案')
                    saved = writer.get(job.candidate_id)
                    self.assertEqual((saved.status, saved.caption), ('test_in_progress', '人工核准的測試文案'))

    def test_finished_reply_after_processing_deadline_is_not_published(self):
        from datetime import timedelta
        self.meta.ready = 'IN_PROGRESS'
        with self.workflow() as workflow:
            job = self.prepared(workflow)
            workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.now += timedelta(minutes=6)
            self.meta.ready = 'FINISHED'
            result = workflow.instagram_test_publish(job.id, self.publisher(), confirmed=True)
            self.assertEqual(result.status, 'blocked')
            self.assertEqual(sum(p.endswith('/media_publish') for _, p, _ in self.meta.posts), 0)
