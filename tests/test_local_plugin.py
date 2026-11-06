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
            # Synthetic receipts prove installed CLI integration, not real Meta scheduling.
            job = invoke('native-prepare', identifier, '--revision', str(approved[0]['revision']))
            intent = invoke('native-begin', job['id'], '--revision', str(job['revision']),
                            '--action', 'create', '--confirm-operation')
            self.assertEqual(invoke('native-get', job['id'])['status'], 'unknown')
            from datetime import datetime, timezone
            proof = root / 'synthetic-proof.png'
            proof.write_bytes(b'synthetic UI fixture, not actual platform evidence')
            receipt = root / 'native-receipt.json'
            receipt.write_text(json.dumps(dict(receipt_id='installed-cli-synthetic',
                operation_id=intent['operation_id'], result='scheduled', native_schedule_id='synthetic-schedule',
                account_id=job['account_id'], username=job['username'], caption=job['caption'],
                scheduled_for=job['scheduled_for'], media_fingerprint=job['media_fingerprint'],
                checked_at=datetime.now(timezone.utc).isoformat(),
                source_url='https://business.facebook.com/latest/posts/scheduled_posts',
                evidence_path=str(proof), reloaded=True, upload_complete=True, public=True, instagram_only=True)))
            saved = invoke('native-observe', job['id'], '--receipt', str(receipt))
            self.assertEqual(saved['status'], 'scheduled')
            self.assertIsNone(saved['media_id'])
            self.assertEqual(invoke('native-list')[0]['id'], job['id'])
            self.assertTrue(movie.exists())
            self.assertEqual(list(published.iterdir()), [])
            self.assertFalse(invoke('chat-disable')['enabled'])
            for arguments in (['instagram-check'], ['instagram-diagnose', '--business-id', '793333293126263'],
                              ['instagram-test-prepare', 'unapproved', '--revision', '1', '--page-id', '1424349244092893', '--api-version', 'v26.0'],
                              ['instagram-test-publish', 'unapproved', '--confirm-publish-now'],
                              ['instagram-test-schedule', 'unapproved', '--at', '2099-01-01T20:00:00+08:00', '--confirm-schedule'],
                              ['instagram-test-run', 'unapproved']):
                blocked = subprocess.run(prefix + arguments, cwd=root, capture_output=True, text=True)
                self.assertEqual(blocked.returncode, 2)
            self.assertEqual(list(published.iterdir()), [])
