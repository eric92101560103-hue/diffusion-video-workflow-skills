from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import unittest
import zipfile


class LocalPluginTests(unittest.TestCase):
    def test_installed_package_runs_local_review_without_credentials_or_repository_imports(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'plugin.zip'
            built = subprocess.run([sys.executable, 'scripts/build_local_plugin.py', '--output', str(package)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            with zipfile.ZipFile(package) as archive:
                self.assertFalse(any('.env' in name or '.venv/' in name or name.endswith('.sqlite3') for name in archive.namelist()))
                archive.extractall(root / 'installed')
            marketplace = root / 'installed' / 'diffusion-reels-local-marketplace'
            catalog = json.loads((marketplace / '.agents/plugins/marketplace.json').read_text())
            plugin = marketplace / catalog['plugins'][0]['source']['path']
            manifest = json.loads((plugin / 'plugin.json').read_text())
            self.assertTrue(manifest['extensions']['com.openai']['requires_local_executor'])
            self.assertTrue((plugin / 'skills/diffusion-tc-subtitles/references/shared-controls.tsx').is_file())
            source, published = root / 'input', root / 'archive'
            source.mkdir()
            published.mkdir()
            state = root / 'state.sqlite3'
            prefix = [sys.executable, '-I', '-S', str(plugin / 'scripts/reels.py'), '--source', str(source),
                      '--published', str(published), '--database', str(state)]
            def invoke(*args, expected=0):
                result = subprocess.run(prefix + list(args), cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                return json.loads(result.stdout)
            preflight = invoke('preflight')
            self.assertFalse(preflight['configured'])
            self.assertFalse(state.exists())
            self.assertFalse(invoke('chat-setup', '--first-scan', '2020-01-01T08:00:00+08:00')['enabled'])
            invoke('chat-enable', '--confirm-primary')
            # Actual synthetic video; all media and state remain temporary.
            movie = source / '測試影片.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=32x32:r=1',
                            '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(movie)], check=True)
            import os
            import time
            os.utime(movie, (time.time() - 60, time.time() - 60))
            first = invoke('chat-check')
            receipt = first['notification']
            self.assertEqual(receipt['status'], 'unconfirmed')
            invoke('chat-resolve', receipt['id'], '--outcome', 'received', '--confirm-checked')
            self.assertIsNone(invoke('chat-check')['notification'])
            candidates = invoke('list')
            self.assertEqual(len(candidates), 1)
            identifier = candidates[0]['id']
            invoke('caption', identifier, '--text', '明確核准的測試文案')
            plan = invoke('preview', identifier, '--first-date', '2099-01-01')
            versions = root / 'versions.json'
            versions.write_text(json.dumps({identifier: plan[0]['revision']}))
            approved = invoke('approve', '--versions-file', str(versions))
            self.assertEqual(approved[0]['status'], 'approved')
            self.assertTrue(movie.exists())
            self.assertEqual(list(published.iterdir()), [])
            self.assertFalse(invoke('chat-disable')['enabled'])
            blocked = subprocess.run(prefix + ['instagram-check'], cwd=root, capture_output=True, text=True)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertEqual(list(published.iterdir()), [])
