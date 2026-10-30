"""Read-only account preflight. OAuth and real publishing remain deployment blockers."""

from dataclasses import dataclass, field
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
        request = Request(f'https://{host}/{self.version}/{path}',
                          headers={'Authorization': f'Bearer {self.token}'})
        try:
            with build_opener(NoRedirects()).open(request, timeout=30) as response:
                data = json.loads(response.read(1024 * 1024))
        except HTTPError as error:
            codes: list[str] = []
            try:
                failure = json.loads(error.read(65536))
                detail = failure.get('error') if isinstance(failure, dict) else None
                if isinstance(detail, dict):
                    codes = [str(detail[key]) for key in ('code', 'error_subcode')
                             if type(detail.get(key)) is int]
            except (OSError, ValueError):
                pass
            finally:
                error.close()
            diagnostic = f'，Meta {"/".join(codes)}' if codes else ''
            raise ValueError(f'IG 帳號檢查失敗（HTTP {error.code}{diagnostic}）；請核對登入、權限與資產授權，未執行發佈') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ValueError('IG 帳號檢查未取得可核對結果；未執行任何發佈') from None
        if self.login == 'unified' and isinstance(data, dict):
            accounts = data.get('data')
            if not isinstance(accounts, list):
                raise ValueError('統一登入的 IG 帳號清單格式無法核對')
            if not accounts:
                raise ValueError('統一登入未列出任何 IG 帳號；請核對指定資產授權，未執行發佈')
            matches = [item for item in accounts
                       if isinstance(item, dict) and item.get('id') == self.account_id]
            if len(matches) != 1:
                raise ValueError('統一登入清單未能唯一核對配置的 IG 帳號；請以 API 回傳的帳號 ID 配置')
            data = matches[0]
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
