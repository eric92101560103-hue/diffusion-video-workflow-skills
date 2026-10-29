from reel_publisher import WorkflowError
from reel_publisher.instagram import Account
from tests.test_workflow import WorkflowTests


class Connection:
    def __init__(self, username):
        self.username = username

    def account(self):
        return Account('123456', self.username)


class InstagramCheckTests(WorkflowTests):
    def test_account_check_matches_exact_target_and_never_claims_publishing_permission(self):
        with self.workflow() as workflow:
            result = workflow.check_instagram(Connection('_eric_han'))
            self.assertEqual(result.username, '_eric_han')
            with self.assertRaisesRegex(WorkflowError, '帳號不符'):
                workflow.check_instagram(Connection('someone_else'))
            self.assertEqual(workflow.list_candidates(), [])


if __name__ == '__main__':
    import unittest
    unittest.main()
