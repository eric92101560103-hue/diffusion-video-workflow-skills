from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import plistlib
import sys

from reel_publisher.cli import main
from tests.support import WorkflowFixture


class ScanServiceTests(WorkflowFixture):
    def test_prepare_creates_private_inactive_bundle_without_scanning(self):
        output = self.root / 'service'
        arguments = ['--source', str(self.source), '--published', str(self.archive),
                     '--database', str(self.config.database), 'scan-service-prepare',
                     '--directory', str(output), '--first-scan', '2026-11-03T10:00:00+08:00']
        self.video()
        stream = StringIO()
        with redirect_stdout(stream):
            self.assertEqual(main(arguments), 0)
        result = json.loads(stream.getvalue())
        self.assertFalse(result['enabled'])
        self.assertFalse(self.config.database.exists())
        plist = plistlib.loads((output / 'local.reel-publisher.scan.plist').read_bytes())
        self.assertEqual(plist['StartInterval'], 60)
        self.assertTrue(plist['RunAtLoad'])
        self.assertEqual(plist['ProgramArguments'][0], sys.executable)
        self.assertNotIn('EnvironmentVariables', plist)
        self.assertEqual((output / 'settings.json').stat().st_mode & 0o777, 0o600)
        self.assertIn('--confirm-enable', (output / 'enable.sh').read_text())
        self.assertIn('bootout', (output / 'disable.sh').read_text())
        # Preparing twice cannot overwrite a reviewed configuration.
        with redirect_stderr(StringIO()):
            self.assertEqual(main(arguments), 1)

    def test_check_rejects_secrets_and_accepts_complete_nonsecret_settings_without_delivery(self):
        from reel_publisher.scan_service import prepare, run
        output = self.root / 'service'
        prepare(self.config, output, self.now)
        settings_path = output / 'settings.json'
        settings = json.loads(settings_path.read_text())
        settings['smtp'] = {'REEL_SMTP_HOST': 'smtp.invalid', 'REEL_EMAIL_FROM': 'sender@example.invalid',
                            'REEL_EMAIL_TO': 'owner@example.invalid', 'REEL_SMTP_USERNAME': 'user',
                            'REEL_SMTP_KEYCHAIN_SERVICE': 'explicit-test-service'}
        settings_path.write_text(json.dumps(settings))
        stream = StringIO()
        with redirect_stdout(stream):
            self.assertEqual(run(settings_path, check=True), 0)
        self.assertEqual(json.loads(stream.getvalue())['credentials'], 'not_checked')
        self.assertFalse(self.config.database.exists())
        settings['smtp']['REEL_SMTP_PASSWORD'] = 'do-not-display'
        settings_path.write_text(json.dumps(settings))
        stream = StringIO()
        with redirect_stderr(stream):
            self.assertEqual(run(settings_path, check=True), 1)
        self.assertNotIn('do-not-display', stream.getvalue())

    def test_generated_scripts_parse_and_enable_requires_explicit_confirmation(self):
        import subprocess
        from reel_publisher.scan_service import prepare
        output = self.root / "private service's directory"
        prepare(self.config, output, self.now)
        for script in ('enable.sh', 'disable.sh'):
            result = subprocess.run(['sh', '-n', str(output / script)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(['sh', str(output / 'enable.sh')], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.config.database.exists())

    def test_old_bundle_cannot_stop_a_different_installed_service(self):
        import os
        import shlex
        import subprocess
        from reel_publisher.scan_service import LABEL, prepare
        output = self.root / 'bundle'
        prepare(self.config, output, self.now)
        installed = self.root / 'isolated-launch-agents'
        installed.mkdir()
        (installed / f'{LABEL}.plist').write_text('different reviewed bundle')
        binary = self.root / 'stub-bin'
        binary.mkdir()
        calls = self.root / 'launchctl-calls'
        stub = binary / 'launchctl'
        stub.write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> ' + shlex.quote(str(calls)) + '\n')
        stub.chmod(0o700)
        # Change only the target directory; never point a test at the real LaunchAgents.
        script = self.root / 'isolated-disable.sh'
        script.write_text((output / 'disable.sh').read_text().replace(
            '$HOME/Library/LaunchAgents', str(installed)))
        result = subprocess.run(['sh', str(script)], capture_output=True,
                                env={**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH']})
        self.assertEqual(result.returncode, 1)
        self.assertFalse(calls.exists(), calls.read_text() if calls.exists() else '')
        self.assertTrue((installed / f'{LABEL}.plist').exists())
