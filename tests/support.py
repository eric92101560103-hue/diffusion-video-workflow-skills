from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from reel_publisher import Config, Workflow


class WorkflowFixture(unittest.TestCase):
    """Shared setup only: no inherited test cases or duplicate discovery."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / '待發佈'
        self.archive = self.root / '已發佈'
        self.source.mkdir()
        self.archive.mkdir()
        self.now = datetime(2026, 11, 1, 2, tzinfo=timezone.utc)
        self.config = Config(self.root / 'state.sqlite3', self.source, self.archive)

    def video(self, name='reel.mp4', content=b'completed video', directory=None):
        path = (directory or self.source) / name
        path.write_bytes(content)
        os.utime(path, (self.now.timestamp() - 60, self.now.timestamp() - 60))
        return path

    def workflow(self):
        return Workflow(self.config, now=lambda: self.now, inspect_media=lambda path: None)
