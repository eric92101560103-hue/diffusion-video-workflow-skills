"""Preparation-only: synthetic media and a fake platform, never network or real IG."""
from datetime import date, datetime, timezone
from reel_publisher.cloud_prototype import CloudPrototype, SimulatedPlatform
from tests.support import WorkflowFixture


class CloudPreparationTests(WorkflowFixture):
    def release(self, name='one.mp4', content=b'fake media'):
        self.video(name, content)
        with self.workflow() as workflow:
            candidate = workflow.scan().discovered[0]
            workflow.set_caption(candidate.id, '使用者確認的模擬文案')
            plan = workflow.preview([candidate.id], first_date=date(2026, 11, 3))
            workflow.approve({candidate.id: plan[0].revision})
            return workflow.export_release(candidate.id)

    def cloud(self, platform):
        return CloudPrototype(self.root / 'cloud', platform, now=lambda: self.now)

    def test_upload_is_separate_from_activation_and_runs_with_local_workflow_closed(self):
        release = self.release()
        platform = SimulatedPlatform()
        with self.cloud(platform) as cloud:
            job = cloud.upload(release)
            self.assertEqual(job.status, 'uploaded')
            self.assertEqual(cloud.upload(release).id, job.id)
            cloud.run()
            self.assertEqual(platform.published, [])
            cloud.activate(job.id)
        self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        with self.cloud(platform) as cloud:
            cloud.run()
            result = cloud.get(job.id)
            self.assertEqual(result.status, 'succeeded')
            self.assertTrue(result.simulated)
            self.assertEqual(len(platform.published), 1)
            cloud.run()
            self.assertEqual(len(platform.published), 1)

    def test_lost_success_response_is_reconciled_without_second_publish(self):
        class LostResponse(SimulatedPlatform):
            def publish(self, job_id, caption, media):
                super().publish(job_id, caption, media)
                raise TimeoutError('private provider details')
        release = self.release()
        platform = LostResponse()
        with self.cloud(platform) as cloud:
            job = cloud.upload(release)
            cloud.activate(job.id)
        self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        with self.cloud(platform) as cloud:
            self.assertEqual(cloud.run()[0].status, 'unknown')
            self.assertEqual(cloud.run()[0].status, 'unknown')
            cloud.reconcile(job.id)
            self.assertEqual(cloud.get(job.id).status, 'succeeded')
            self.assertEqual(len(platform.published), 1)

    def test_only_confirmed_not_published_can_retry_and_deadline_is_exclusive(self):
        from reel_publisher.cloud_prototype import NotPublished
        class TemporaryFailure(SimulatedPlatform):
            def publish(self, job_id, caption, media):
                raise NotPublished('temporary')
        release = self.release()
        platform = TemporaryFailure()
        with self.cloud(platform) as cloud:
            job = cloud.upload(release)
            cloud.activate(job.id)
            self.now = datetime(2026, 11, 3, 12, 29, tzinfo=timezone.utc)
            self.assertEqual(cloud.run()[0].status, 'retry_wait')
        platform = SimulatedPlatform()
        self.now = datetime(2026, 11, 3, 12, 30, tzinfo=timezone.utc)
        with self.cloud(platform) as cloud:
            self.assertEqual(cloud.run()[0].status, 'expired')
            self.assertEqual(platform.published, [])

    def test_cancel_keeps_other_dates_and_never_publishes_cancelled_job(self):
        first = self.release()
        second = self.release('two.mp4', b'second fake media')
        platform = SimulatedPlatform()
        with self.cloud(platform) as cloud:
            one, two = cloud.upload(first), cloud.upload(second)
            cloud.activate(one.id)
            cloud.activate(two.id)
            self.assertEqual(cloud.cancel(one.id).status, 'cancelled')
            self.assertEqual(cloud.cancel(one.id).status, 'cancelled')
            self.assertEqual(cloud.get(two.id).release.scheduled_for, '2026-11-05T20:00:00+08:00')
            self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
            cloud.run()
            self.assertEqual(platform.published, [])

    def test_success_archive_never_overwrites_local_file_or_republishes(self):
        release = self.release()
        platform = SimulatedPlatform()
        with self.cloud(platform) as cloud:
            job = cloud.upload(release)
            cloud.activate(job.id)
            self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
            cloud.run()
            target = self.archive / 'one.mp4'
            target.write_bytes(b'other local video')
            self.assertEqual(cloud.archive(job.id, self.archive), 'conflict')
            self.assertEqual(target.read_bytes(), b'other local video')
            self.assertEqual(cloud.get(job.id).status, 'succeeded')
            target.unlink()
            self.assertEqual(cloud.archive(job.id, self.archive), 'archived')
            self.assertEqual(cloud.archive(job.id, self.archive), 'archived')
            self.assertFalse((self.source / 'one.mp4').exists())
            cloud.run()
            self.assertEqual(len(platform.published), 1)

    def test_cleanup_waits_seven_days_and_preserves_receipt_and_local_media(self):
        from datetime import timedelta
        release = self.release()
        platform = SimulatedPlatform()
        with self.cloud(platform) as cloud:
            job = cloud.upload(release)
            cloud.activate(job.id)
            self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
            cloud.run()
            self.now += timedelta(days=7, microseconds=-1)
            self.assertEqual(cloud.cleanup(), {})
            self.now += timedelta(microseconds=1)
            self.assertEqual(cloud.cleanup(), {job.id: 'deleted'})
            self.assertEqual(cloud.cleanup(), {job.id: 'deleted'})
            self.assertTrue((self.source / 'one.mp4').exists())
            self.assertIsNotNone(cloud.get(job.id).media_id)
            self.assertEqual(cloud.get(job.id).status, 'succeeded')

    def test_process_death_after_publish_is_unknown_until_reconciled_and_cancel_cannot_claim_success(self):
        class ProcessDied(SimulatedPlatform):
            def publish(self, job_id, caption, media):
                super().publish(job_id, caption, media)
                raise KeyboardInterrupt()
        release = self.release()
        platform = ProcessDied()
        with self.cloud(platform) as cloud:
            job = cloud.upload(release)
            cloud.activate(job.id)
            self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
            with self.assertRaises(KeyboardInterrupt):
                cloud.run()
        with self.cloud(platform) as cloud:
            self.assertEqual(cloud.cancel(job.id).status, 'publishing')
            self.assertEqual(cloud.run()[0].status, 'unknown')
            self.assertEqual(len(platform.published), 1)
            self.assertEqual(cloud.reconcile(job.id).status, 'succeeded')
            self.assertEqual(cloud.cancel(job.id).status, 'succeeded')

    def test_unknown_and_active_shared_media_are_retained_past_cleanup_deadline(self):
        from dataclasses import replace
        from datetime import timedelta
        first = self.release()
        platform = SimulatedPlatform()
        with self.cloud(platform) as cloud:
            one = cloud.upload(first)
            cloud.activate(one.id)
            # Simulate a separately reviewed explicit replay sharing the same media bytes.
            replay = replace(first, candidate_id='explicit-replay', scheduled_for='2026-11-13T20:00:00+08:00')
            two = cloud.upload(replay)
            cloud.activate(two.id)
            self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
            cloud.run()
            self.now += timedelta(days=7)
            self.assertEqual(cloud.cleanup(), {one.id: 'retained_shared'})
            self.assertEqual(cloud.get(two.id).status, 'active')
            self.assertTrue((self.root / 'cloud' / 'simulation-media' / first.fingerprint).exists())

    def test_unapproved_or_modified_content_cannot_be_exported_for_upload(self):
        from reel_publisher import WorkflowError
        self.video()
        with self.workflow() as workflow:
            candidate = workflow.scan().discovered[0]
            with self.assertRaises(WorkflowError):
                workflow.export_release(candidate.id)
            workflow.set_caption(candidate.id, '核准前文案')
            plan = workflow.preview([candidate.id], first_date=date(2026, 11, 3))
            workflow.approve({candidate.id: plan[0].revision})
            self.video(content=b'different edit')
            with self.assertRaises(WorkflowError):
                workflow.export_release(candidate.id)

    def test_revised_caption_stops_old_version_and_requires_new_approval_and_activation(self):
        release = self.release()
        platform = SimulatedPlatform()
        with self.cloud(platform) as cloud:
            old = cloud.upload(release)
            cloud.activate(old.id)
        with self.workflow() as workflow:
            changed = workflow.set_caption(release.candidate_id, '修改後文案')
            from reel_publisher import WorkflowError
            with self.assertRaises(WorkflowError):
                workflow.export_release(changed.id)
            workflow.approve({changed.id: changed.revision})
            reviewed = workflow.export_release(changed.id)
        with self.cloud(platform) as cloud:
            revised = cloud.replace(old.id, reviewed)
            self.assertEqual(cloud.get(old.id).status, 'cancelled')
            self.assertEqual(revised.status, 'uploaded')
            cloud.activate(revised.id)
            self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
            cloud.run()
            self.assertEqual(platform.published, [revised.id])

    def test_incident_mail_failure_is_visible_and_never_changes_platform_result(self):
        class UnknownPlatform(SimulatedPlatform):
            def publish(self, job_id, caption, media):
                raise TimeoutError('private')
        class Mailbox:
            def __init__(self):
                self.messages = []
            def send_incident(self, job_id, status):
                self.messages.append((job_id, status))
                raise TimeoutError('private smtp')
        platform, mailbox = UnknownPlatform(), Mailbox()
        release = self.release()
        with self.cloud(platform) as cloud:
            job = cloud.upload(release)
            cloud.activate(job.id)
            self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
            cloud.run()
            self.assertEqual(cloud.send_alerts(mailbox), {job.id: 'unknown'})
            cloud.send_alerts(mailbox)
            self.assertEqual(len(mailbox.messages), 1)
            self.assertEqual(cloud.get(job.id).status, 'unknown')
