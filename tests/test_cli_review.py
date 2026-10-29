from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import subprocess
import unittest

from reel_publisher.cli import main


class ReviewCommandTests(unittest.TestCase):
    def test_user_can_fill_caption_preview_and_confirm_without_cloud_activation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, archive = root / '待發佈', root / '已發佈'
            source.mkdir()
            archive.mkdir()
            video = source / 'sample.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=32x32:r=1',
                '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video),
            ], check=True)
            timestamp = video.stat().st_mtime - 60
            os.utime(video, (timestamp, timestamp))
            prefix = ['--source', str(source), '--published', str(archive), '--database', str(root / 'db.sqlite3')]

            def run(arguments):
                output, errors = StringIO(), StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    code = main(prefix + arguments)
                self.assertEqual(code, 0, errors.getvalue())
                return json.loads(output.getvalue())

            candidate = run(['scan'])['discovered'][0]
            run(['caption', candidate['id'], '--text', '測試文案 #Reels'])
            first_date = (datetime.now().date() + timedelta(days=2)).isoformat()
            plan = run(['preview', candidate['id'], '--first-date', first_date])
            versions = root / 'review.json'
            versions.write_text(json.dumps({plan[0]['id']: plan[0]['revision']}))
            approved = run(['approve', '--versions-file', str(versions)])
            self.assertEqual(approved[0]['status'], 'approved')
            self.assertEqual(approved[0]['caption'], '測試文案 #Reels')
            self.assertTrue(video.exists())
            self.assertEqual(list(archive.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
