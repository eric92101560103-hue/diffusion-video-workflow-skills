"""IG fixtures replace only the HTTP service; assertions use the shared Workflow."""

from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError

from reel_publisher.instagram import InstagramConnection
from tests.support import WorkflowFixture


class MetaResponse(BytesIO):
    def __init__(self, data):
        super().__init__(json.dumps(data).encode())


class MetaService:
    def __init__(self, data):
        self.data = data
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return MetaResponse(self.data)


class InstagramConnectionTests(WorkflowFixture):
    def test_unified_login_identifies_instagram_account_not_system_user(self):
        service = MetaService({'data': [{'id': '17841403997461963', 'username': '_eric_han'}]})
        connection = InstagramConnection('17841403997461963', 'v26.0', 'test-only-token', 'unified')
        with patch('reel_publisher.instagram.build_opener', return_value=service):
            with self.workflow() as workflow:
                account = workflow.check_instagram(connection)
                self.assertEqual((account.id, account.username), ('17841403997461963', '_eric_han'))
                self.assertEqual(workflow.list_candidates(), [])
        request = service.requests[0]
        self.assertIn('/me/assigned_instagram_accounts?', request.full_url)
        self.assertTrue(request.full_url.startswith('https://graph.facebook.com/v26.0/'))
        self.assertNotIn('test-only-token', request.full_url)

    def test_instagram_login_uses_professional_user_id_not_app_scoped_id(self):
        service = MetaService({'id': '999', 'user_id': '17841403997461963', 'username': '_eric_han'})
        connection = InstagramConnection('17841403997461963', 'v26.0', 'test-only-token', 'instagram')
        with patch('reel_publisher.instagram.build_opener', return_value=service):
            with self.workflow() as workflow:
                account = workflow.check_instagram(connection)
                self.assertEqual(account.id, '17841403997461963')
        self.assertEqual(service.requests[0].full_url,
                         'https://graph.instagram.com/v26.0/me?fields=user_id,username')

    def test_instagram_login_accepts_documented_single_account_envelope(self):
        service = MetaService({'data': [{'user_id': '17841403997461963', 'username': '_eric_han'}]})
        connection = InstagramConnection('17841403997461963', 'v26.0', 'test-only-token', 'instagram')
        with patch('reel_publisher.instagram.build_opener', return_value=service):
            with self.workflow() as workflow:
                self.assertEqual(workflow.check_instagram(connection).username, '_eric_han')

    def test_invalid_connection_settings_fail_before_any_http_request(self):
        for account_id, version, login in [('123', 'v26.0', 'unknown'),
                                            ('123/other', 'v26.0', 'unified'),
                                            ('123', 'v26.0/other', 'unified')]:
            with self.subTest(login=login, account_id=account_id, version=version):
                with self.assertRaises(ValueError):
                    InstagramConnection(account_id, version, 'test-only-token', login)

    def test_meta_failure_reports_only_numeric_codes_and_does_not_echo_secret(self):
        payload = {'error': {'code': 100, 'error_subcode': 33,
                             'message': 'test-only-token https://unsafe.example/token'}}
        service = MetaService({})
        error = HTTPError('https://graph.facebook.com/', 400, 'Bad request', {}, MetaResponse(payload))
        connection = InstagramConnection('17841403997461963', 'v26.0', 'test-only-token', 'unified')
        with patch('reel_publisher.instagram.build_opener', return_value=service):
            with patch.object(service, 'open', side_effect=error):
                with self.workflow() as workflow:
                    with self.assertRaisesRegex(ValueError, '100/33') as caught:
                        workflow.check_instagram(connection)
                    self.assertNotIn('test-only-token', str(caught.exception))
                    self.assertNotIn('unsafe.example', str(caught.exception))

    def test_unified_empty_or_ambiguous_assets_are_blocked_without_secret_output(self):
        target = {'id': '17841403997461963', 'username': '_eric_han'}
        for payload, reason in [({'data': []}, '未列出任何 IG 帳號'),
                                ({'data': [target, target]}, '唯一核對'),
                                ({'data': [{'id': '999', 'username': '_eric_han'}]}, '唯一核對'),
                                ({'id': '17841403997461963', 'username': '_eric_han'}, '清單格式')]:
            with self.subTest(payload=payload):
                service = MetaService(payload)
                connection = InstagramConnection('17841403997461963', 'v26.0', 'test-only-token', 'unified')
                with patch('reel_publisher.instagram.build_opener', return_value=service):
                    with self.workflow() as workflow:
                        with self.assertRaisesRegex(ValueError, reason) as caught:
                            workflow.check_instagram(connection)
                        self.assertNotIn('test-only-token', str(caught.exception))
                        self.assertEqual(workflow.list_candidates(), [])

    def test_unified_environment_is_explicit_and_facebook_route_remains_supported(self):
        environment = {'REEL_IG_ACCOUNT_ID': '17841403997461963', 'REEL_IG_API_VERSION': 'v26.0',
                       'REEL_IG_LOGIN': 'unified', 'REEL_IG_ACCESS_TOKEN': 'test-only-token'}
        with patch.dict('os.environ', environment, clear=True):
            connection = InstagramConnection.from_environment()
            self.assertEqual(connection.login, 'unified')
            self.assertNotIn('test-only-token', repr(connection))
        service = MetaService({'id': '17841403997461963', 'username': '_eric_han'})
        with patch('reel_publisher.instagram.build_opener', return_value=service):
            with self.workflow() as workflow:
                account = workflow.check_instagram(InstagramConnection(
                    '17841403997461963', 'v26.0', 'test-only-token', 'facebook'))
                self.assertEqual(account.username, '_eric_han')
        self.assertEqual(service.requests[0].full_url,
                         'https://graph.facebook.com/v26.0/17841403997461963?fields=id,username')
