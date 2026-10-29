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


@dataclass(frozen=True)
class InstagramConnection:
    account_id: str
    version: str
    token: str = field(repr=False)
    login: str = 'instagram'

    @classmethod
    def from_environment(cls) -> 'InstagramConnection':
        account_id = os.environ.get('REEL_IG_ACCOUNT_ID', '')
        version = os.environ.get('REEL_IG_API_VERSION', '')
        login = os.environ.get('REEL_IG_LOGIN', 'instagram')
        if not account_id.isdecimal() or not re.fullmatch(r'v[0-9]+\.0', version):
            raise ValueError('請先設定授權後的 IG 帳號 ID 與經核實的 API 版本')
        if login not in ('instagram', 'facebook'):
            raise ValueError('登入類型必須為 instagram 或 facebook')
        token = runtime_secret('REEL_IG_ACCESS_TOKEN',
                               keychain_service=os.environ.get('REEL_IG_KEYCHAIN_SERVICE'),
                               account=account_id)
        if not token:
            raise ValueError('尚未配置 IG 授權；請先完成 Meta 應用程式及官方授權流程')
        return cls(account_id, version, token, login)

    def account(self) -> Account:
        host = 'graph.instagram.com' if self.login == 'instagram' else 'graph.facebook.com'
        request = Request(f'https://{host}/{self.version}/{self.account_id}?fields=id,username',
                          headers={'Authorization': f'Bearer {self.token}'})
        try:
            with build_opener(NoRedirects()).open(request, timeout=30) as response:
                data = json.loads(response.read(1024 * 1024))
        except HTTPError as error:
            raise ValueError(f'IG 帳號檢查失敗（HTTP {error.code}）；請核對登入、權限與版本') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ValueError('IG 帳號檢查未取得可核對結果；未執行任何發佈') from None
        if not isinstance(data, dict) or not isinstance(data.get('id'), str) or not isinstance(data.get('username'), str):
            raise ValueError('IG 帳號回應格式無法核對；未執行任何發佈')
        if data['id'] != self.account_id:
            raise ValueError('授權帳號 ID 與配置不符')
        return Account(data['id'], data['username'])
