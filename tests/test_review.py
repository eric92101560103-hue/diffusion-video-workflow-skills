from datetime import date, datetime, timezone

from reel_publisher import WorkflowError
from tests.test_workflow import WorkflowTests


class ReviewTests(WorkflowTests):
    def candidates(self):
        self.video('one.mp4', b'first completed video')
        self.video('two.mp4', b'second completed video')
        with self.workflow() as workflow:
            return list(workflow.scan().discovered)

    def test_caption_order_and_dates_survive_confirmation_and_restart(self):
        first, second = self.candidates()
        with self.workflow() as workflow:
            workflow.set_caption(first.id, '第一支 #生活')
            workflow.set_caption(second.id, '第二支')
            plan = workflow.preview([second.id, first.id], first_date=date(2026, 11, 3))
            self.assertEqual([item.scheduled_for for item in plan],
                             ['2026-11-03T20:00:00+08:00', '2026-11-05T20:00:00+08:00'])
            approved = workflow.approve({item.id: item.revision for item in plan})
            self.assertEqual([item.status for item in approved], ['approved', 'approved'])
        with self.workflow() as workflow:
            self.assertEqual(workflow.get(first.id).caption, '第一支 #生活')
            self.assertEqual(workflow.get(second.id).scheduled_for, '2026-11-03T20:00:00+08:00')

    def test_incomplete_batch_never_partially_approves(self):
        first, second = self.candidates()
        with self.workflow() as workflow:
            workflow.set_caption(first.id, '完整文案')
            plan = workflow.preview([first.id, second.id], first_date=date(2026, 11, 3))
            with self.assertRaisesRegex(WorkflowError, '文案'):
                workflow.approve({item.id: item.revision for item in plan})
            self.assertEqual(workflow.get(first.id).status, 'candidate')
            self.assertEqual(workflow.get(second.id).status, 'candidate')

    def test_caption_edit_invalidates_approval_and_old_review_version(self):
        first, _ = self.candidates()
        with self.workflow() as workflow:
            workflow.set_caption(first.id, '原文案')
            plan = workflow.preview([first.id], first_date=date(2026, 11, 3))
            workflow.approve({first.id: plan[0].revision})
            edited = workflow.set_caption(first.id, '新文案')
            self.assertEqual(edited.status, 'candidate')
            self.assertIsNone(edited.approval_revision)
            with self.assertRaisesRegex(WorkflowError, '版本'):
                workflow.approve({first.id: plan[0].revision})

    def test_changed_video_cannot_use_review_for_old_content(self):
        first, _ = self.candidates()
        with self.workflow() as workflow:
            workflow.set_caption(first.id, '文案')
            plan = workflow.preview([first.id], first_date=date(2026, 11, 3))
            self.video('one.mp4', b'edited content')
            with self.assertRaisesRegex(WorkflowError, '內容已變更'):
                workflow.approve({first.id: plan[0].revision})
            self.assertEqual(workflow.get(first.id).status, 'candidate')

    def test_expired_draft_requires_new_review_and_keeps_calendar_rhythm(self):
        first, _ = self.candidates()
        with self.workflow() as workflow:
            workflow.set_caption(first.id, '文案')
            plan = workflow.preview([first.id], first_date=date(2026, 11, 3))
            self.now = datetime(2026, 11, 4, 2, tzinfo=timezone.utc)
            with self.assertRaisesRegex(WorkflowError, '日期已過'):
                workflow.approve({first.id: plan[0].revision})
            refreshed = workflow.preview([first.id])
            self.assertEqual(refreshed[0].scheduled_for, '2026-11-05T20:00:00+08:00')
            with self.assertRaisesRegex(WorkflowError, '版本'):
                workflow.approve({first.id: plan[0].revision})

    def test_new_batch_appends_and_competing_drafts_cannot_share_slot(self):
        first, second = self.candidates()
        with self.workflow() as workflow:
            workflow.set_caption(first.id, '第一支')
            workflow.set_caption(second.id, '第二支')
            first_plan = workflow.preview([first.id], first_date=date(2026, 11, 3))
            second_plan = workflow.preview([second.id])
            workflow.approve({first.id: first_plan[0].revision})
            with self.assertRaisesRegex(WorkflowError, '時段已被'):
                workflow.approve({second.id: second_plan[0].revision})
            appended = workflow.preview([second.id])
            self.assertEqual(appended[0].scheduled_for, '2026-11-05T20:00:00+08:00')
            self.assertEqual(workflow.get(first.id).scheduled_for, '2026-11-03T20:00:00+08:00')


if __name__ == '__main__':
    import unittest
    unittest.main()
