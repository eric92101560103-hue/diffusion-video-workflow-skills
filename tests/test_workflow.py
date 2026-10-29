from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import os
import unittest

from reel_publisher import Config, Workflow
from tests.support import WorkflowFixture


class WorkflowTests(WorkflowFixture):

    def test_scan_makes_new_video_retrievable_without_moving_or_publishing(self):
        path = self.video()
        with self.workflow() as workflow:
            result = workflow.scan()
            self.assertEqual(len(result.discovered), 1)
            candidate = workflow.get(result.discovered[0].id)
            self.assertEqual(candidate.status, 'candidate')
            self.assertEqual(candidate.path, str(path.resolve()))
            self.assertIsNone(candidate.caption)
            self.assertEqual(workflow.list_candidates(), [candidate])
        self.assertTrue(path.exists())
        with self.workflow() as workflow:
            self.assertEqual(workflow.get(candidate.id), candidate)

    def test_explicit_replay_is_required_for_archived_or_renamed_content(self):
        self.video('old.mp4', directory=self.archive)
        self.video('renamed.mp4')
        with self.workflow() as workflow:
            self.assertEqual(workflow.scan().discovered, ())
            self.assertEqual(workflow.list_candidates(), [])
            replay = workflow.replay(self.source / 'renamed.mp4', confirmed=True)
            self.assertEqual(replay.status, 'candidate')
            self.assertEqual(len(workflow.scan().discovered), 0)
            self.assertEqual(len(workflow.list_candidates()), 1)

    def test_renaming_pending_video_updates_its_location_without_duplicate(self):
        path = self.video()
        with self.workflow() as workflow:
            original = workflow.scan().discovered[0]
            renamed = path.rename(self.source / 'new-name.mp4')
            self.assertEqual(workflow.scan().discovered, ())
            self.assertEqual(workflow.get(original.id).path, str(renamed.resolve()))
            self.assertEqual(len(workflow.list_candidates()), 1)

    def test_unstable_invalid_and_symlink_inputs_are_not_candidates(self):
        fresh = self.video('fresh.mp4')
        os.utime(fresh, (self.now.timestamp(), self.now.timestamp()))
        outside = self.video('outside.mp4', directory=self.root)
        (self.source / 'link.mp4').symlink_to(outside)
        self.video('empty.mov', b'')
        with self.workflow() as workflow:
            result = workflow.scan()
            self.assertEqual(result.discovered, ())
            self.assertEqual(len(result.skipped), 3)

    def test_empty_source_is_safe_and_missing_archive_fails_closed(self):
        with self.workflow() as workflow:
            self.assertEqual(workflow.scan().discovered, ())
            self.archive.rmdir()
            self.video()
            with self.assertRaisesRegex(Exception, '已發佈資料夾'):
                workflow.scan()
            self.assertEqual(workflow.list_candidates(), [])

    def test_archived_duplicate_exposes_local_evidence_without_platform_claim(self):
        archived = self.video('old.mp4', directory=self.archive)
        self.video('renamed.mp4')
        with self.workflow() as workflow:
            result = workflow.scan()
            self.assertEqual(result.skipped[0].evidence, 'local_archive')
            self.assertEqual(result.skipped[0].reference, str(archived))
            self.assertFalse(result.skipped[0].platform_verified)

    def test_simultaneous_first_launches_can_all_read_the_same_state(self):
        for attempt in range(8):
            config = Config(self.root / f'concurrent-{attempt}.sqlite3', self.source, self.archive)
            barrier = Barrier(8)

            def start(_):
                barrier.wait()
                with Workflow(config) as workflow:
                    return workflow.list_candidates()

            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(list(pool.map(start, range(8))), [[]] * 8)


if __name__ == '__main__':
    unittest.main()
