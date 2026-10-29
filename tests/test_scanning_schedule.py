from datetime import datetime, timedelta, timezone

from tests.test_workflow import WorkflowTests


class Mailbox:
    def __init__(self):
        self.messages = []

    def send(self, notice):
        self.messages.append(notice)


class ScanScheduleTests(WorkflowTests):
    def test_every_two_days_discovers_new_candidates_and_notifies_once(self):
        self.video()
        mailbox = Mailbox()
        anchor = datetime(2026, 11, 1, 2, tzinfo=timezone.utc)
        with self.workflow() as workflow:
            result = workflow.tick(first_scan=anchor, notifier=mailbox)
            self.assertTrue(result.scanned)
            self.assertEqual(len(mailbox.messages), 1)
            self.assertEqual(mailbox.messages[0].candidate_id, workflow.list_candidates()[0].id)
            self.assertEqual(workflow.notification_status()[0].status, 'sent')
        with self.workflow() as workflow:
            self.assertFalse(workflow.tick(first_scan=anchor, notifier=mailbox).scanned)
            self.now += timedelta(days=1)
            self.assertFalse(workflow.tick(first_scan=anchor, notifier=mailbox).scanned)
            self.now += timedelta(days=1)
            self.assertTrue(workflow.tick(first_scan=anchor, notifier=mailbox).scanned)
            self.assertEqual(len(mailbox.messages), 1)
            self.assertEqual(workflow.list_candidates()[0].status, 'candidate')

    def test_missed_scans_catch_up_once_and_keep_original_two_day_calendar(self):
        mailbox = Mailbox()
        anchor = datetime(2026, 11, 1, 2, tzinfo=timezone.utc)
        self.now = datetime(2026, 11, 6, 2, tzinfo=timezone.utc)
        self.video()
        with self.workflow() as workflow:
            result = workflow.tick(first_scan=anchor, notifier=mailbox)
            self.assertTrue(result.scanned)
            self.assertEqual(result.next_scan, '2026-11-07T10:00:00+08:00')
            self.assertEqual(len(mailbox.messages), 1)
            self.assertFalse(workflow.tick(first_scan=anchor, notifier=mailbox).scanned)

    def test_failed_email_is_visible_and_not_blindly_resent(self):
        class FailingMailbox:
            def send(self, notice):
                raise TimeoutError('secret must not be stored or shown')
        anchor = self.now
        self.video()
        with self.workflow() as workflow:
            result = workflow.tick(first_scan=anchor, notifier=FailingMailbox())
            self.assertEqual(result.notifications[0].status, 'unknown')
            self.assertEqual(len(workflow.list_candidates()), 1)
        mailbox = Mailbox()
        with self.workflow() as workflow:
            result = workflow.tick(first_scan=anchor, notifier=mailbox)
            self.assertEqual(result.notifications[0].status, 'unknown')
            self.assertEqual(mailbox.messages, [])

    def test_empty_folder_does_not_send_email_and_future_scan_waits(self):
        mailbox = Mailbox()
        with self.workflow() as workflow:
            future = self.now + timedelta(days=2)
            result = workflow.tick(first_scan=future, notifier=mailbox)
            self.assertFalse(result.scanned)
            self.assertEqual(mailbox.messages, [])
            self.now = future
            self.assertTrue(workflow.tick(first_scan=future, notifier=mailbox).scanned)
            self.assertEqual(mailbox.messages, [])


if __name__ == '__main__':
    import unittest
    unittest.main()
