"""Read-only diagnostic CLI tested against the external Meta HTTP boundary."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from reel_publisher.cli import main
from tests.test_instagram_connection import MetaResponse


class MetaDiagnosticsService:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return MetaResponse(reply)


class InstagramDiagnosticTests(unittest.TestCase):
    def invoke(self, replies, **settings):
        environment = {'REEL_IG_ACCOUNT_ID': '17841403997461963', 'REEL_IG_API_VERSION': 'v26.0',
                       'REEL_IG_LOGIN': 'unified', 'REEL_IG_ACCESS_TOKEN': 'fixture-secret-only'}
        environment.update(settings)
        service = MetaDiagnosticsService(replies)
        with TemporaryDirectory() as directory:
            database = Path(directory) / 'must-not-be-created.sqlite3'
            output, errors = StringIO(), StringIO()
            with patch.dict('os.environ', environment, clear=True), redirect_stdout(output), redirect_stderr(errors):
                with patch('reel_publisher.instagram.build_opener', return_value=service):
                    code = main(['--database', str(database), 'instagram-diagnose',
                                 '--business-id', '793333293126263'])
            self.assertFalse(database.exists())
        text = output.getvalue() + errors.getvalue()
        self.assertNotIn('fixture-secret-only', text)
        return code, json.loads(text), service.requests

    def test_diagnostic_verifies_business_and_account_without_creating_local_state(self):
        code, report, requests = self.invoke([
            {'id': '122099677641529995', 'client_business_id': '793333293126263'},
            {'data': [{'id': '17841403997461963', 'username': '_eric_han'}]},
        ])
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'identity_verified')
        self.assertEqual(report['business_id'], '793333293126263')
        self.assertEqual(report['account'], {'id': '17841403997461963', 'username': '_eric_han'})
        self.assertEqual(report['publishing_permission'], 'not_verified')
        self.assertFalse(report['published'])
        self.assertEqual([r.get_method() for r in requests], ['GET', 'GET'])
        self.assertTrue(all('fixture-secret-only' not in r.full_url for r in requests))

    def test_second_stage_oauth_failure_preserves_verified_business_and_redacts_service_details(self):
        from urllib.error import HTTPError
        failure = HTTPError('https://graph.facebook.com/?access_token=fixture-secret-only', 400, 'bad', {},
                            MetaResponse({'error': {'code': 190, 'message': 'fixture-secret-only',
                                                    'fbtrace_id': 'TRACE_test_190_001'}}))
        code, report, _ = self.invoke([{'client_business_id': '793333293126263'}, failure])
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'request_failed')
        self.assertEqual(report['business_id'], '793333293126263')
        self.assertEqual(report['stage'], 'assigned_instagram_accounts')
        self.assertIn('190', report['error'])
        self.assertIn('TRACE_test_190_001', report['error'])

    def test_changed_account_id_is_reported_for_review_without_silently_changing_configuration(self):
        code, report, _ = self.invoke([
            {'client_business_id': '793333293126263'},
            {'data': [{'id': '999123', 'username': '_eric_han'}],
             'paging': {'next': 'https://unsafe.example/?access_token=fixture-secret-only'}},
        ])
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'account_id_mismatch')
        self.assertEqual(report['observed_account'], {'id': '999123', 'username': '_eric_han'})
        self.assertFalse(report['accounts_page_complete'])
        self.assertIsNone(report['account'])

    def test_empty_assets_identifies_the_failed_stage_after_business_is_verified(self):
        code, report, _ = self.invoke([
            {'client_business_id': '793333293126263'}, {'data': []},
        ])
        self.assertEqual(code, 1)
        self.assertEqual(report['business_id'], '793333293126263')
        self.assertEqual(report['status'], 'no_accounts_in_response')
        self.assertEqual(report['stage'], 'assigned_instagram_accounts')
        self.assertIsNone(report['account'])
        self.assertFalse(report['published'])

    def test_wrong_business_stops_before_reading_instagram_assets(self):
        code, report, requests = self.invoke([{'client_business_id': '999123'}])
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'business_mismatch')
        self.assertEqual(report['business_id'], '999123')
        self.assertIsNone(report['account'])
        self.assertEqual(len(requests), 1)

    def test_wrong_username_and_duplicate_or_malformed_accounts_never_verify_identity(self):
        cases = [
            ({'data': [{'id': '17841403997461963', 'username': 'another_account'}]}, 'username_mismatch'),
            ({'data': [{'id': '17841403997461963', 'username': '_eric_han'}] * 2},
             'account_not_uniquely_identified'),
            ({'data': [{'id': 'fixture-secret-only', 'username': '_eric_han'}]}, 'request_failed'),
            ({'data': [{'id': '123', 'username': 'https://fixture-secret-only.example/'}]}, 'request_failed'),
            ([], 'request_failed'),
        ]
        for assets, expected in cases:
            with self.subTest(expected=expected):
                code, report, _ = self.invoke([{'client_business_id': '793333293126263'}, assets])
                self.assertEqual(code, 1)
                self.assertEqual(report['status'], expected)

    def test_other_login_modes_cannot_send_unified_diagnostic_requests(self):
        code, report, requests = self.invoke([], REEL_IG_LOGIN='instagram')
        self.assertEqual(code, 1)
        self.assertIn('unified', report['error'])
        self.assertEqual(requests, [])

    def test_keychain_wait_timeout_requests_os_confirmation_without_claiming_invalid_token(self):
        import subprocess
        with patch('reel_publisher.secrets.subprocess.run',
                   side_effect=subprocess.TimeoutExpired('security', 60)):
            code, report, requests = self.invoke([], REEL_IG_ACCESS_TOKEN='',
                                                REEL_IG_KEYCHAIN_SERVICE='fixture-service')
        self.assertEqual(code, 1)
        self.assertIn('逾時', report['error'])
        self.assertIn('macOS', report['error'])
        self.assertEqual(requests, [])

    def test_error_tracking_does_not_echo_a_secret_or_url_disguised_as_a_trace_id(self):
        from urllib.error import HTTPError
        for trace in ('fixture-secret-only', 'https://fixture-secret-only.example/', 'x' * 65):
            failure = HTTPError('https://graph.facebook.com/', 400, 'bad', {},
                                MetaResponse({'error': {'code': 190, 'fbtrace_id': trace}}))
            code, report, _ = self.invoke([failure])
            self.assertEqual(code, 1)
            self.assertEqual(report['stage'], 'client_business_id')
            self.assertNotIn('追蹤', report['error'])
