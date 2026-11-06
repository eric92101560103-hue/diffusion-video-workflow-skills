from datetime import date
from tests.support import WorkflowFixture
from reel_publisher.workflow import WorkflowError


class NativeSchedulingTests(WorkflowFixture):
    def approved(self, workflow, name='first.mp4', content=b'first'):
        self.video(name, content)
        candidate = workflow.scan().discovered[0]
        workflow.set_caption(candidate.id, '核准文案')
        plan = workflow.preview([candidate.id], first_date=date(2026, 11, 3))[0]
        return workflow.approve({candidate.id: plan.revision})[0]

    def test_native_reservation_survives_restart_and_cannot_be_recreated(self):
        with self.workflow() as workflow:
            candidate = self.approved(workflow)
            job = workflow.native_prepare(candidate.id, candidate.revision)
            self.assertEqual(job.status, 'prepared')
            self.assertEqual(workflow.get(candidate.id).status, 'native_pending')
        with self.workflow() as workflow:
            self.assertEqual(workflow.native_get(job.id).caption, '核准文案')
            with self.assertRaises(WorkflowError):
                workflow.native_prepare(candidate.id, candidate.revision)
            with self.assertRaises(WorkflowError):
                workflow.replay(self.source / 'first.mp4', confirmed=True)
            with self.assertRaises(WorkflowError):
                workflow.set_caption(candidate.id, '意外改文案')

    def receipt(self, job, **changes):
        from reel_publisher.native_scheduling import NativeObservation
        proof = self.root / 'proof.png'
        proof.write_bytes(b'isolated synthetic proof, not real Meta evidence')
        values = dict(receipt_id='receipt-1', operation_id=job.operation_id, result='scheduled',
                      native_schedule_id='schedule-100', account_id=job.account_id, username=job.username,
                      caption=job.proposed_caption or job.caption, scheduled_for=job.proposed_for or job.scheduled_for,
                      media_fingerprint=job.media_fingerprint, checked_at=self.now.isoformat(),
                      source_url='https://business.facebook.com/latest/posts/scheduled_posts',
                      evidence_path=str(proof), reloaded=True, upload_complete=True, public=True, instagram_only=True)
        values.update(changes)
        return NativeObservation(**values)

    def test_unknown_operation_fences_restart_and_receipt_requires_exact_reload(self):
        with self.workflow() as workflow:
            candidate = self.approved(workflow)
            job = workflow.native_prepare(candidate.id, candidate.revision)
            operation = workflow.native_begin(job.id, job.revision, action='create', confirmed=True)
        with self.workflow() as workflow:
            with self.assertRaises(WorkflowError):
                workflow.native_begin(job.id, operation.revision, action='create', confirmed=True)
            for changes in ({'reloaded': False}, {'caption': '遺失或錯誤文案'}, {'username': 'wrong'},
                            {'scheduled_for': '2026-11-05T20:00:00+08:00'}):
                with self.assertRaises(WorkflowError):
                    workflow.native_observe(job.id, self.receipt(operation, **changes))
            saved = workflow.native_observe(job.id, self.receipt(operation))
            self.assertEqual(saved.status, 'scheduled')
            self.assertEqual(saved.native_schedule_id, 'schedule-100')
            self.assertIsNone(saved.media_id)
            self.assertEqual(workflow.native_observe(job.id, self.receipt(operation)), saved)
            self.assertEqual(workflow.get(candidate.id).status, 'native_scheduled')

    def scheduled(self, workflow):
        candidate = self.approved(workflow)
        job = workflow.native_prepare(candidate.id, candidate.revision)
        operation = workflow.native_begin(job.id, job.revision, action='create', confirmed=True)
        return workflow.native_observe(job.id, self.receipt(operation))

    def test_cancel_race_keeps_actual_published_result_and_other_dates(self):
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            other = self.approved(workflow, 'other.mp4', b'other')
            pending = workflow.native_begin(job.id, job.revision, action='cancel', confirmed=True)
            with self.assertRaises(WorkflowError):
                workflow.native_observe(job.id, self.receipt(pending, receipt_id='cancelled', result='cancelled'))
            published = workflow.native_observe(job.id, self.receipt(pending, receipt_id='published',
                result='published', media_id='ig-media-900', permalink='https://www.instagram.com/reel/actual/',
                published_at=self.now.isoformat()))
            self.assertEqual(published.status, 'published')
            self.assertEqual(workflow.get(other.id).scheduled_for, other.scheduled_for)
            with self.assertRaises(WorkflowError):
                workflow.native_begin(job.id, published.revision, action='cancel', confirmed=True)

    def test_modify_race_accepts_proven_old_content_and_does_not_claim_new_content(self):
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            pending = workflow.native_begin(job.id, job.revision, action='modify', confirmed=True, caption='新核准文案')
            actual = workflow.native_observe(job.id, self.receipt(pending, receipt_id='raced', result='published',
                caption='核准文案', media_id='ig-media-901', permalink='https://www.instagram.com/reel/raced/',
                published_at=self.now.isoformat()))
            self.assertEqual(actual.status, 'published')
            self.assertEqual(actual.caption, '核准文案')

    def test_only_proven_success_archives_and_conflict_preserves_source(self):
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            with self.assertRaises(WorkflowError):
                workflow.native_archive(job.id)
            job = workflow.native_observe(job.id, self.receipt(job, receipt_id='pub', result='published',
                media_id='media-900', permalink='https://www.instagram.com/reel/published/', published_at=self.now.isoformat()))
            target = self.archive / 'first.mp4'
            target.write_bytes(b'other film')
            with self.assertRaises(WorkflowError):
                workflow.native_archive(job.id)
            self.assertEqual(target.read_bytes(), b'other film')
            self.assertTrue((self.source / 'first.mp4').exists())
            target.unlink()
            result = workflow.native_archive(job.id)
            self.assertEqual(result.archived_path, str(target.resolve()))
            self.assertFalse((self.source / 'first.mp4').exists())
            self.assertEqual(target.read_bytes(), b'first')
            self.assertEqual(workflow.native_archive(job.id), result)

    def test_scan_surfaces_overdue_once_without_retry_and_cleanup_is_terminal_only(self):
        from datetime import datetime, timezone
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            with self.assertRaises(WorkflowError):
                workflow.native_cleanup(job.id, confirmed=True)
            workflow.chat_setup(first_scan=datetime(2026, 11, 1, 0, tzinfo=timezone.utc))
            workflow.chat_enable(confirmed=True)
            self.now = datetime(2026, 11, 3, 12, 29, 59, tzinfo=timezone.utc)
            self.assertEqual(workflow.native_check(), [])
            self.now = datetime(2026, 11, 3, 12, 30, tzinfo=timezone.utc)
            self.assertEqual(len(workflow.native_check()), 1)
            report = workflow.chat_check().notification
            self.assertEqual(report.items[0].kind, 'native_attention')
            self.assertEqual(len(workflow.native_check()), 1)
            self.assertIsNone(workflow.chat_check().notification)
            self.assertEqual(workflow.native_get(job.id).status, 'scheduled')

    def test_published_identity_is_immutable(self):
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            saved = workflow.native_observe(job.id, self.receipt(job, receipt_id='pub-a', result='published',
                media_id='media-a', permalink='https://www.instagram.com/reel/a/', published_at=self.now.isoformat()))
            with self.assertRaises(WorkflowError):
                workflow.native_observe(job.id, self.receipt(saved, receipt_id='pub-b', result='published',
                    media_id='media-b', permalink='https://www.instagram.com/reel/b/', published_at=self.now.isoformat()))
            self.assertEqual(workflow.native_get(job.id).media_id, 'media-a')

    def test_archive_does_not_delete_source_replaced_after_final_fingerprint_read(self):
        from pathlib import Path
        from unittest.mock import patch
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            job = workflow.native_observe(job.id, self.receipt(job, receipt_id='pub-race', result='published',
                media_id='media-race', permalink='https://www.instagram.com/reel/race/', published_at=self.now.isoformat()))
            source = Path(job.source_path)
            destination = self.archive / source.name
            real_stat = Path.stat
            reads = 0
            def replace_after_stat(path, *args, **kwargs):
                nonlocal reads
                result = real_stat(path, *args, **kwargs)
                if path == source and destination.exists() and kwargs.get('follow_symlinks', True):
                    reads += 1
                    if reads == 3:
                        source.write_bytes(b'new user film')
                return result
            with patch.object(Path, 'stat', replace_after_stat):
                try:
                    workflow.native_archive(job.id)
                except WorkflowError:
                    pass
            self.assertTrue(source.exists(), '並行替換的新原片不能被刪除')
            self.assertEqual(source.read_bytes(), b'new user film')

    def test_unknown_modification_reserves_both_dates_for_new_candidates(self):
        from datetime import datetime
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            workflow.native_begin(job.id, job.revision, action='modify', confirmed=True,
                scheduled_for=datetime.fromisoformat('2026-11-07T20:00:00+08:00'))
            other = self.approved(workflow, 'second.mp4', b'second')
            self.assertEqual(other.scheduled_for, '2026-11-09T20:00:00+08:00')

    def test_successful_cancel_releases_only_own_slot_and_cleanup_preserves_original(self):
        from pathlib import Path
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            other = self.approved(workflow, 'other.mp4', b'other')
            pending = workflow.native_begin(job.id, job.revision, action='cancel', confirmed=True)
            saved = workflow.native_observe(job.id, self.receipt(pending, receipt_id='cancel-ok', result='cancelled',
                cancellation_confirmed=True))
            self.assertEqual(saved.status, 'cancelled')
            workflow.native_cleanup(job.id, confirmed=True)
            self.assertFalse(Path(job.media_path).exists())
            self.assertEqual((self.source / 'first.mp4').read_bytes(), b'first')
            self.assertEqual(workflow.get(other.id).scheduled_for, other.scheduled_for)
            self.assertEqual(workflow.native_cleanup(job.id, confirmed=True).status, 'cancelled')

    def test_modified_schedule_persists_new_content_without_rearranging_other_video(self):
        from datetime import datetime
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            other = self.approved(workflow, 'other.mp4', b'other')
            changed = workflow.native_begin(job.id, job.revision, action='modify', confirmed=True,
                caption='新文案', scheduled_for=datetime.fromisoformat('2026-11-07T20:00:00+08:00'))
            saved = workflow.native_observe(job.id, self.receipt(changed, receipt_id='modify-ok'))
            self.assertEqual(saved.caption, '新文案')
            self.assertEqual(saved.scheduled_for, '2026-11-07T20:00:00+08:00')
            self.assertEqual(workflow.get(other.id).scheduled_for, other.scheduled_for)
        with self.workflow() as workflow:
            self.assertEqual(workflow.native_get(job.id).caption, '新文案')

    def test_failed_and_unknown_observations_never_grant_retry_permission(self):
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            for result in ('failed', 'unknown'):
                saved = workflow.native_observe(job.id, self.receipt(job, receipt_id=result, result=result))
                with self.assertRaises(WorkflowError):
                    workflow.native_begin(job.id, saved.revision, action='create', confirmed=True)
                with self.assertRaises(WorkflowError):
                    workflow.native_archive(job.id)
                with self.assertRaises(WorkflowError):
                    workflow.replay(self.source / 'first.mp4', confirmed=True)

    def test_changed_upload_copy_blocks_create(self):
        from pathlib import Path
        with self.workflow() as workflow:
            candidate = self.approved(workflow)
            job = workflow.native_prepare(candidate.id, candidate.revision)
            Path(job.media_path).write_bytes(b'changed upload')
            with self.assertRaises(WorkflowError):
                workflow.native_begin(job.id, job.revision, action='create', confirmed=True)
            self.assertEqual(workflow.native_get(job.id).status, 'prepared')

    def test_changed_original_after_preparation_blocks_create(self):
        with self.workflow() as workflow:
            candidate = self.approved(workflow)
            job = workflow.native_prepare(candidate.id, candidate.revision)
            (self.source / 'first.mp4').write_bytes(b'unreviewed new source')
            with self.assertRaises(WorkflowError):
                workflow.native_begin(job.id, job.revision, action='create', confirmed=True)

    def test_confirmed_rejected_modification_can_recover_old_schedule_once(self):
        from datetime import datetime, timezone
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            workflow.chat_setup(first_scan=datetime(2026, 11, 1, 0, tzinfo=timezone.utc))
            workflow.chat_enable(confirmed=True)
            pending = workflow.native_begin(job.id, job.revision, action='modify', confirmed=True, caption='新文案')
            first = workflow.chat_check().notification
            saved = workflow.native_observe(job.id, self.receipt(pending, receipt_id='rejected-edit',
                caption='核准文案', operation_not_applied=True))
            self.assertEqual(saved.caption, '核准文案')
            recovered = workflow.chat_check().notification
            self.assertEqual(recovered.items[0].kind, 'native_recovery')
            self.assertIn(first.id, workflow.chat_check().unconfirmed_report_ids)
            self.assertIsNone(workflow.chat_check().notification)

    def test_archive_partial_copy_recovers_on_restart(self):
        from unittest.mock import patch
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            job = workflow.native_observe(job.id, self.receipt(job, receipt_id='pub-copy', result='published',
                media_id='media-copy', permalink='https://www.instagram.com/reel/copy/', published_at=self.now.isoformat()))
            def interrupt_copy(source, destination):
                destination.write(source.read(2))
                raise OSError('simulated process interruption')
            with patch('shutil.copyfileobj', interrupt_copy):
                with self.assertRaises(OSError):
                    workflow.native_archive(job.id)
            self.assertTrue((self.source / 'first.mp4').exists())
        with self.workflow() as workflow:
            result = workflow.native_archive(job.id)
            self.assertIsNotNone(result.archived_path)
            self.assertEqual((self.archive / 'first.mp4').read_bytes(), b'first')
            self.assertFalse((self.source / 'first.mp4').exists())

    def test_archive_source_handoff_recovers_after_process_interruption(self):
        from unittest.mock import patch
        import os
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            job = workflow.native_observe(job.id, self.receipt(job, receipt_id='pub-handoff', result='published',
                media_id='media-handoff', permalink='https://www.instagram.com/reel/handoff/', published_at=self.now.isoformat()))
            real_rename = os.rename
            def interrupt_after_handoff(*args, **kwargs):
                real_rename(*args, **kwargs)
                raise OSError('simulated process loss after atomic source handoff')
            with patch('os.rename', interrupt_after_handoff):
                with self.assertRaises(OSError):
                    workflow.native_archive(job.id)
            self.assertIsNone(workflow.native_get(job.id).archived_path)
        with self.workflow() as workflow:
            result = workflow.native_archive(job.id)
            self.assertIsNotNone(result.archived_path)
            self.assertEqual((self.archive / 'first.mp4').read_bytes(), b'first')
            self.assertFalse((self.source / 'first.mp4').exists())

    def test_stale_revision_and_parallel_begin_never_grant_second_external_write(self):
        with self.workflow() as first, self.workflow() as second:
            candidate = self.approved(first)
            job = first.native_prepare(candidate.id, candidate.revision)
            reserved = second.native_begin(job.id, job.revision, action='create', confirmed=True)
            with self.assertRaises(WorkflowError):
                first.native_begin(job.id, job.revision, action='create', confirmed=True)
            self.assertEqual(first.native_get(job.id).operation_id, reserved.operation_id)

    def test_receipt_cannot_claim_future_or_wrong_media_and_schedule_identity(self):
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            for values in ({'checked_at': '2099-01-01T00:00:00+00:00'},
                           {'native_schedule_id': 'different-schedule'}, {'media_fingerprint': 'different-film'},
                           {'source_url': 'https://business.facebook.com/latest/posts/?access_token=do-not-store'},
                           {'reloaded': 'true'}, {'instagram_only': False}):
                with self.assertRaises(WorkflowError):
                    workflow.native_observe(job.id, self.receipt(job, receipt_id='bad', **values))
            self.assertEqual(workflow.native_get(job.id).status, 'scheduled')

    def test_expired_prepared_job_can_withdraw_locally_but_unknown_job_cannot(self):
        from datetime import timedelta
        with self.workflow() as workflow:
            candidate = self.approved(workflow)
            job = workflow.native_prepare(candidate.id, candidate.revision)
            self.now += timedelta(days=5)
            saved = workflow.native_withdraw(job.id, confirmed=True)
            self.assertEqual(saved.status, 'withdrawn')
            fresh = workflow.replay(self.source / 'first.mp4', confirmed=True)
            self.assertEqual(fresh.status, 'candidate')
            workflow.native_cleanup(job.id, confirmed=True)
            workflow.set_caption(fresh.id, '新核准文案')
            plan = workflow.preview([fresh.id])[0]
            candidate = workflow.approve({fresh.id: plan.revision})[0]
            other = workflow.native_prepare(candidate.id, candidate.revision)
            pending = workflow.native_begin(other.id, other.revision, action='create', confirmed=True)
            with self.assertRaises(WorkflowError):
                workflow.native_withdraw(pending.id, confirmed=True)

    def test_destination_changed_during_handoff_retains_original_recovery_copy(self):
        from pathlib import Path
        from unittest.mock import patch
        import os
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            job = workflow.native_observe(job.id, self.receipt(job, receipt_id='pub-destination', result='published',
                media_id='media-destination', permalink='https://www.instagram.com/reel/destination/', published_at=self.now.isoformat()))
            target = self.archive / 'first.mp4'
            real_rename = os.rename
            def change_destination(*args, **kwargs):
                target.write_bytes(b'destination changed by external editor')
                return real_rename(*args, **kwargs)
            with patch('os.rename', change_destination):
                with self.assertRaises(WorkflowError):
                    workflow.native_archive(job.id)
            current = workflow.native_get(job.id)
            self.assertIsNone(current.archived_path)
            self.assertEqual(Path(current.recovery_path).read_bytes(), b'first')

    def test_browser_blocker_is_durable_without_changing_platform_result(self):
        from datetime import datetime, timezone
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            workflow.chat_setup(first_scan=datetime(2026, 11, 1, 0, tzinfo=timezone.utc))
            workflow.chat_enable(confirmed=True)
            blocked = workflow.native_blocked(job.id, 'login_required')
            with self.assertRaises(WorkflowError):
                workflow.native_begin(job.id, blocked.revision, action='cancel', confirmed=True)
            first = workflow.chat_check().notification
            self.assertEqual(first.items[0].kind, 'native_attention')
            self.assertEqual(workflow.native_get(job.id).status, 'scheduled')
        with self.workflow() as workflow:
            workflow.native_blocked(job.id, 'login_required')
            self.assertIsNone(workflow.chat_check().notification)
            workflow.native_observe(job.id, self.receipt(job, receipt_id='browser-recovered'))
            self.assertEqual(workflow.chat_check().notification.items[0].kind, 'native_recovery')

    def test_stale_platform_receipt_cannot_clear_new_browser_blocker(self):
        from datetime import timedelta
        with self.workflow() as workflow:
            job = self.scheduled(workflow)
            old_checked = self.now.isoformat()
            self.now += timedelta(hours=1)
            blocked = workflow.native_blocked(job.id, 'login_required')
            with self.assertRaises(WorkflowError):
                workflow.native_observe(job.id, self.receipt(job, receipt_id='stale-new-id', checked_at=old_checked))
            self.assertEqual(workflow.native_get(job.id).check_problem, 'login_required')
            self.now += timedelta(hours=1)
            repeated = workflow.native_blocked(job.id, 'login_required')
            self.assertEqual(repeated.revision, blocked.revision)
            saved = workflow.native_observe(job.id, self.receipt(job, receipt_id='fresh-check'))
            self.assertIsNone(saved.check_problem)
