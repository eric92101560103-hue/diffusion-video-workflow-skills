from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import subprocess
import sys
import time
import unittest


class CommandTests(unittest.TestCase):
    def test_real_video_scan_is_read_only_and_invalid_video_is_reported(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, archive = root / '待發佈', root / '已發佈'
            source.mkdir()
            archive.mkdir()
            video = source / 'sample.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=32x32:r=1',
                '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video),
            ], check=True)
            broken = source / 'broken.mp4'
            broken.write_bytes(b'not a video')
            for path in [video, broken]:
                os.utime(path, (time.time() - 60, time.time() - 60))
            prefix = [sys.executable, '-m', 'reel_publisher', '--source', str(source),
                      '--published', str(archive), '--database', str(root / 'state.sqlite3')]
            scanned = subprocess.run(prefix + ['scan'], capture_output=True, text=True, check=True)
            result = json.loads(scanned.stdout)
            self.assertEqual(len(result['discovered']), 1)
            self.assertEqual(len(result['skipped']), 1)
            self.assertEqual(result['discovered'][0]['status'], 'candidate')
            listed = subprocess.run(prefix + ['list'], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(listed.stdout), result['discovered'])
            self.assertTrue(video.exists())
            self.assertEqual(list(archive.iterdir()), [])
            scanned_again = subprocess.run(prefix + ['scan'], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(scanned_again.stdout)['discovered'], [])


if __name__ == '__main__':
    unittest.main()
