from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from io import StringIO
import json

from reel_publisher.cli import main
from tests.support import WorkflowFixture


class ChatCommandTests(WorkflowFixture):
    def arguments(self, *command):
        return ['--source', str(self.source), '--published', str(self.archive),
                '--database', str(self.config.database), *command]

    def test_cli_does_not_assume_output_reached_user_after_broken_output(self):
        class BrokenOutput:
            def write(self, value):
                raise BrokenPipeError('output closed')
        self.video('影片"換行\n.mp4')
        with self.workflow() as workflow:
            workflow.scan()
            workflow.chat_setup(first_scan=datetime(2099, 1, 1, tzinfo=timezone.utc))
            workflow.chat_enable(confirmed=True)
        with redirect_stdout(BrokenOutput()), redirect_stderr(StringIO()):
            self.assertEqual(main(self.arguments('chat-check')), 1)
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(self.arguments('chat-check')), 0)
        result = json.loads(output.getvalue())
        self.assertIsNone(result['notification'])
        self.assertEqual(len(result['unconfirmed_report_ids']), 1)
        with self.workflow() as workflow:
            report = workflow.chat_report(result['unconfirmed_report_ids'][0])
            self.assertEqual(report.items[0].filename, '影片"換行\n.mp4')
            self.assertEqual(report.status, 'unconfirmed')

    def test_preflight_does_not_create_state_and_reports_unconfigured(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(self.arguments('preflight')), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result['configured'])
        self.assertFalse(result['enabled'])
        self.assertFalse(result['publishing_available'])
        self.assertFalse(self.config.database.exists())
