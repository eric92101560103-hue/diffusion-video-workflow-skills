"""Read-only account preflight. OAuth and real publishing remain deployment blockers."""

from dataclasses import asdict, dataclass, field
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import json
import os
import re

from .secrets import runtime_secret


@dataclass(frozen=True)
class Account:
    id: str
    username: str


class InstagramAccountReader(Protocol):
    def account(self) -> Account: ...


class NoRedirects(HTTPRedirectHandler):
    # Preserve Authorization only for the explicitly configured Meta host.
    def redirect_request(self, req: Request, fp: object, code: int, msg: str,
                         headers: object, newurl: str) -> None:
        return None


def _validate_settings(account_id: str, version: str, login: str) -> None:
    if not account_id.isdecimal() or not re.fullmatch(r'v[0-9]+\.0', version):
        raise ValueError('請先設定授權後的 IG 帳號 ID 與經核實的 API 版本')
    if login not in ('instagram', 'facebook', 'unified'):
        raise ValueError('登入類型必須為 instagram、facebook 或 unified')


def _assigned_accounts(data: object) -> tuple[list[Account], bool]:
    if not isinstance(data, dict) or not isinstance(data.get('data'), list):
        raise ValueError('統一登入的 IG 帳號清單格式無法核對')
    accounts = []
    for item in data['data']:
        if not isinstance(item, dict):
            raise ValueError('統一登入的 IG 帳號格式無法核對')
        identifier, username = item.get('id'), item.get('username')
        if (not isinstance(identifier, str) or not identifier.isascii() or not identifier.isdecimal()
                or not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9._]{1,30}', username)):
            raise ValueError('統一登入的 IG 帳號格式無法核對')
        accounts.append(Account(identifier, username))
    paging = data.get('paging')
    complete = not (isinstance(paging, dict) and paging.get('next'))
    return accounts, complete


@dataclass(frozen=True)
class InstagramConnection:
    account_id: str
    version: str
    token: str = field(repr=False)
    login: str = 'instagram'

    def __post_init__(self) -> None:
        _validate_settings(self.account_id, self.version, self.login)

    @classmethod
    def from_environment(cls) -> 'InstagramConnection':
        account_id = os.environ.get('REEL_IG_ACCOUNT_ID', '')
        version = os.environ.get('REEL_IG_API_VERSION', '')
        login = os.environ.get('REEL_IG_LOGIN', 'instagram')
        _validate_settings(account_id, version, login)
        token = runtime_secret('REEL_IG_ACCESS_TOKEN',
                               keychain_service=os.environ.get('REEL_IG_KEYCHAIN_SERVICE'),
                               account=account_id)
        if not token:
            raise ValueError('尚未配置 IG 授權；請先完成 Meta 應用程式及官方授權流程')
        return cls(account_id, version, token, login)

    def account(self) -> Account:
        host = 'graph.instagram.com' if self.login == 'instagram' else 'graph.facebook.com'
        paths = {
            'unified': 'me/assigned_instagram_accounts?fields=id,username&limit=100',
            'instagram': 'me?fields=user_id,username',
            'facebook': f'{self.account_id}?fields=id,username',
        }
        path = paths[self.login]
        data = self._get_json(host, path)
        if self.login == 'unified':
            accounts, _ = _assigned_accounts(data)
            if not accounts:
                raise ValueError('統一登入未列出任何 IG 帳號；請核對指定資產授權，未執行發佈')
            matches = [item for item in accounts if item.id == self.account_id]
            if len(matches) != 1:
                raise ValueError('統一登入清單未能唯一核對配置的 IG 帳號；請以 API 回傳的帳號 ID 配置')
            data = asdict(matches[0])
        if self.login == 'instagram' and isinstance(data, dict):
            if isinstance(data.get('data'), list):
                accounts = data['data']
                if len(accounts) != 1 or not isinstance(accounts[0], dict):
                    raise ValueError('Instagram 登入回應未能唯一核對帳號')
                data = accounts[0]
            data = {'id': data.get('user_id'), 'username': data.get('username')}
        if not isinstance(data, dict) or not isinstance(data.get('id'), str) or not isinstance(data.get('username'), str):
            raise ValueError('IG 帳號回應格式無法核對；未執行任何發佈')
        if data['id'] != self.account_id:
            raise ValueError('授權帳號 ID 與配置不符')
        return Account(data['id'], data['username'])

    def page_connection(self, page_id: str) -> 'InstagramConnection':
        """Resolve only the explicitly configured Page; never persist its credential."""
        if self.login != 'facebook' or not re.fullmatch(r'[0-9]+', page_id):
            raise ValueError('單支發佈測試需 Facebook 登入與指定專頁編號')
        page = self._get_json('graph.facebook.com',
                              f'{page_id}?fields=id,instagram_business_account,access_token')
        linked = page.get('instagram_business_account') if isinstance(page, dict) else None
        if (not isinstance(page, dict) or page.get('id') != page_id
                or not isinstance(linked, dict) or linked.get('id') != self.account_id):
            raise ValueError('指定專頁未能核對連結的 IG 帳號')
        token = page.get('access_token')
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise ValueError('指定專頁沒有可用的發佈憑證')
        return InstagramConnection(self.account_id, self.version, token, 'facebook')

    def diagnose(self, business_id: str, username: str) -> dict[str, object]:
        if self.login != 'unified' or not business_id.isascii() or not business_id.isdecimal():
            raise ValueError('此診斷需 unified 登入與數字商家編號')
        report: dict[str, object] = {'status': 'identity_verified', 'stage': 'client_business_id', 'business_id': None,
                                    'account': None, 'publishing_permission': 'not_verified', 'published': False}
        try:
            business = self._get_json('graph.facebook.com', 'me?fields=client_business_id')
            actual = business.get('client_business_id') if isinstance(business, dict) else None
            if not isinstance(actual, str) or not actual.isascii() or not actual.isdecimal():
                raise ValueError('商家編號回應格式無法核對')
            report['business_id'] = actual
            if actual != business_id:
                report['status'] = 'business_mismatch'
                return report
            report['stage'] = 'assigned_instagram_accounts'
            data = self._get_json('graph.facebook.com', 'me/assigned_instagram_accounts?fields=id,username&limit=100')
            accounts, complete = _assigned_accounts(data)
            report['accounts_page_complete'] = complete
            if not accounts:
                report['status'] = 'no_accounts_in_response'
                return report
            matches = [item for item in accounts if item.id == self.account_id]
            if len(matches) != 1:
                report['status'] = 'account_not_uniquely_identified'
                observed = [item for item in accounts if item.username == username]
                if not matches and len(observed) == 1:
                    report['status'] = 'account_id_mismatch'
                    report['observed_account'] = asdict(observed[0])
                return report
            report['account'] = asdict(matches[0])
            if matches[0].username != username:
                report['status'] = 'username_mismatch'
            return report
        except ValueError as error:
            report['status'] = 'request_failed'
            report['error'] = str(error)
            return report

    def _get_json(self, host: str, path: str) -> object:
        request = Request(f'https://{host}/{self.version}/{path}',
                          headers={'Authorization': f'Bearer {self.token}'})
        try:
            with build_opener(NoRedirects()).open(request, timeout=30) as response:
                data = json.loads(response.read(1024 * 1024))
        except HTTPError as error:
            codes: list[str] = []
            trace = ''
            try:
                failure = json.loads(error.read(65536))
                detail = failure.get('error') if isinstance(failure, dict) else None
                if isinstance(detail, dict):
                    codes = [str(detail[key]) for key in ('code', 'error_subcode')
                             if type(detail.get(key)) is int]
                    candidate = detail.get('fbtrace_id')
                    if (isinstance(candidate, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', candidate)
                            and self.token not in candidate):
                        trace = f'，追蹤 {candidate}'
            except (OSError, ValueError):
                pass
            finally:
                error.close()
            diagnostic = f'，Meta {"/".join(codes)}' if codes else ''
            raise ValueError(f'IG 帳號檢查失敗（HTTP {error.code}{diagnostic}{trace}）；請核對登入、權限與資產授權，未執行發佈') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ValueError('IG 帳號檢查未取得可核對結果；未執行任何發佈') from None
        return data
