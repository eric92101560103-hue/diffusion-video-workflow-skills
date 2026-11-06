from datetime import timedelta

from reel_publisher import WorkflowError
from tests.support import WorkflowFixture


class ChatNotificationTests(WorkflowFixture):
    def start(self, workflow):
        workflow.chat_setup(first_scan=self.now)
        workflow.chat_enable(confirmed=True)

    def test_discovery_and_delivery_confirmation_are_separate_and_durable(self):
        self.video()
        with self.workflow() as workflow:
            self.start(workflow)
            first = workflow.chat_check()
            self.assertTrue(first.scanned)
            report = first.notification
            self.assertEqual(report.status, 'unconfirmed')
            self.assertEqual(report.items[0].kind, 'candidate')
            self.assertEqual(workflow.get(report.items[0].reference).status, 'candidate')
        with self.workflow() as workflow:
            repeated = workflow.chat_check()
            self.assertIsNone(repeated.notification)
            self.assertEqual(repeated.unconfirmed_report_ids, (report.id,))
            self.assertEqual(workflow.chat_resolve(report.id, outcome='received', confirmed=True).status, 'received')
            self.assertEqual(workflow.chat_resolve(report.id, outcome='received', confirmed=True).status, 'received')
            self.assertIsNone(workflow.chat_check().notification)

    def test_failure_is_reported_once_and_recovery_does_not_consume_missed_slots(self):
        self.source.rmdir()
        with self.workflow() as workflow:
            self.start(workflow)
            failure = workflow.chat_check()
            self.assertEqual(failure.scan_error, 'source_unavailable')
            self.assertEqual(failure.notification.items[0].kind, 'failure')
            self.assertIsNone(workflow.chat_check().notification)
        self.source.mkdir()
        self.video()
        self.now += timedelta(days=5)
        with self.workflow() as workflow:
            recovered = workflow.chat_check()
            self.assertTrue(recovered.scanned)
            self.assertEqual(recovered.next_scan, '2026-11-07T10:00:00+08:00')
            self.assertEqual({item.kind for item in recovered.notification.items}, {'recovery', 'candidate'})
            self.assertIsNone(workflow.chat_check().notification)

    def test_explicit_not_delivered_resolution_requeues_once_but_obsolete_candidates_are_pruned(self):
        from datetime import date
        self.video()
        with self.workflow() as workflow:
            self.start(workflow)
            first = workflow.chat_check().notification
            candidate_id = first.items[0].reference
            with self.assertRaises(WorkflowError):
                workflow.chat_resolve(first.id, outcome='not-delivered')
            workflow.chat_resolve(first.id, outcome='not-delivered', confirmed=True)
            second = workflow.chat_check().notification
            self.assertNotEqual(second.id, first.id)
            self.assertEqual(second.items, first.items)
            workflow.chat_resolve(second.id, outcome='not-delivered', confirmed=True)
            workflow.set_caption(candidate_id, '完整文案')
            plan = workflow.preview([candidate_id], first_date=date(2026, 11, 3))
            workflow.approve({candidate_id: plan[0].revision})
            self.assertIsNone(workflow.chat_check().notification)

    def test_codex_ownership_blocks_smtp_tick_and_disable_stops_checks_without_deleting_candidates(self):
        class NoMail:
            def send(self, notice):
                raise AssertionError('email must not be called')
        self.video()
        with self.workflow() as workflow:
            self.start(workflow)
            workflow.chat_check()
            with self.assertRaisesRegex(WorkflowError, '主要掃描'):
                workflow.tick(first_scan=self.now, notifier=NoMail())
            state = workflow.chat_disable()
            self.assertFalse(state['enabled'])
            with self.assertRaises(WorkflowError):
                workflow.chat_check()
            self.assertEqual(len(workflow.list_candidates()), 1)

    def test_parallel_triggers_claim_one_report_and_unknown_receipt_never_expires(self):
        from concurrent.futures import ThreadPoolExecutor
        self.video()
        with self.workflow() as workflow:
            self.start(workflow)
        def check(_):
            with self.workflow() as workflow:
                return workflow.chat_check()
        with ThreadPoolExecutor(max_workers=6) as workers:
            results = list(workers.map(check, range(6)))
        reports = [result.notification for result in results if result.notification]
        self.assertEqual(len(reports), 1)
        self.assertEqual(sum(result.scanned for result in results), 1)
        self.now += timedelta(days=30)
        with self.workflow() as workflow:
            self.assertIsNone(workflow.chat_check().notification)
            self.assertEqual(workflow.chat_report(reports[0].id).status, 'unconfirmed')

    def test_import_legacy_reported_ids_is_atomic_and_does_not_invent_delivery(self):
        import json
        self.video()
        ledger = self.root / 'legacy-chat-notices.json'
        with self.workflow() as workflow:
            workflow.scan()
            candidate = workflow.list_candidates()[0]
            self.start(workflow)
            ledger.write_text(json.dumps({'reported_candidate_ids': [candidate.id, 'unknown-id']}))
            with self.assertRaises(WorkflowError):
                workflow.chat_import(ledger, confirmed=True)
            self.assertEqual(workflow.chat_status()['unconfirmed_report_ids'], [])
            ledger.write_text(json.dumps({'reported_candidate_ids': [candidate.id]}))
            result = workflow.chat_import(ledger, confirmed=True)
            self.assertEqual(result.status, 'unconfirmed')
            self.assertIsNone(workflow.chat_check().notification)
            self.assertEqual(workflow.chat_import(ledger, confirmed=True).id, result.id)

    def test_scan_interruption_rolls_back_and_restart_can_discover_without_losing_notification(self):
        from reel_publisher import Workflow
        self.video()
        with self.workflow() as workflow:
            self.start(workflow)
        def interrupted_inspection(path):
            raise KeyboardInterrupt()
        with Workflow(self.config, now=lambda: self.now, inspect_media=interrupted_inspection) as workflow:
            with self.assertRaises(KeyboardInterrupt):
                workflow.chat_check()
        with self.workflow() as workflow:
            result = workflow.chat_check()
            self.assertTrue(result.scanned)
            self.assertEqual(len(result.notification.items), 1)
            self.assertIsNone(workflow.chat_check().notification)

    def test_primary_channel_handoff_requires_explicit_confirmation_and_keeps_history(self):
        class SilentMail:
            def send(self, notice):
                raise AssertionError('not due')
        with self.workflow() as workflow:
            workflow.tick(first_scan=self.now + timedelta(days=1), notifier=SilentMail())
            workflow.chat_setup(first_scan=self.now)
            with self.assertRaises(WorkflowError):
                workflow.chat_enable(confirmed=True)
            with self.assertRaises(WorkflowError):
                workflow.scan_release_primary()
            self.assertIsNone(workflow.scan_release_primary(confirmed=True)['primary'])
            self.assertTrue(workflow.chat_enable(confirmed=True)['enabled'])

    def test_corrupt_legacy_json_is_rejected_without_overwriting_reports_or_echoing_contents(self):
        self.video()
        with self.workflow() as workflow:
            self.start(workflow)
            report = workflow.chat_check().notification
            ledger = self.root / 'broken.json'
            for text in ('not-json-private-marker', '{"reported_candidate_ids":true}',
                         '{"reported_candidate_ids":["private-marker","private-marker"]}'):
                ledger.write_text(text)
                with self.assertRaises(WorkflowError) as error:
                    workflow.chat_import(ledger, confirmed=True)
                self.assertNotIn('private-marker', str(error.exception))
                self.assertEqual(workflow.chat_report(report.id).status, 'unconfirmed')
            self.assertIsNone(workflow.chat_check().notification)

    def test_unstable_file_reason_is_visible_and_manual_rescan_does_not_reset_schedule(self):
        import os
        movie = self.video()
        os.utime(movie, (self.now.timestamp(), self.now.timestamp()))
        with self.workflow() as workflow:
            self.start(workflow)
            first = workflow.chat_check()
            self.assertTrue(first.scanned)
            self.assertIsNone(first.notification)
            self.assertEqual(len(first.skipped), 1)
            self.assertIn('穩定', first.skipped[0].reason)
            next_scan = first.next_scan
            self.now += timedelta(seconds=11)
            self.assertEqual(len(workflow.scan().discovered), 1)
            after = workflow.chat_check()
            self.assertFalse(after.scanned)
            self.assertIsNotNone(after.notification)
            self.assertEqual(after.next_scan, next_scan)

    def test_recovered_fault_is_not_reoffered_as_an_active_failure_after_not_delivered(self):
        with self.workflow() as workflow:
            self.start(workflow)
            self.source.rmdir()
            first = workflow.chat_check().notification
            workflow.chat_resolve(first.id, outcome='not-delivered', confirmed=True)
            self.source.mkdir()
            recovered = workflow.chat_check().notification
            self.assertEqual([item.kind for item in recovered.items], ['recovery'])
            self.assertIsNone(workflow.chat_check().notification)
