"""Meta transport for an explicitly approved one-off Reel; no scheduler."""
from dataclasses import dataclass, field
from typing import BinaryIO
import hashlib
import http.client
import json
import re

from .instagram import Account, InstagramConnection


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,64}', value):
        raise ValueError('Meta 未回傳可核對的識別碼')
    return value


@dataclass
class FacebookReels:
    user: InstagramConnection = field(repr=False)
    page_id: str
    _page: InstagramConnection | None = field(default=None, init=False, repr=False)

    @property
    def account_id(self) -> str:
        return self.user.account_id

    @property
    def version(self) -> str:
        return self.user.version

    def account(self) -> Account:
        self._page = self.user.page_connection(self.page_id)
        account = self._page.account()
        if account.username.casefold() != '_eric_han':
            self._page = None
            raise ValueError('發佈帳號不符；僅允許指定的 @_eric_han')
        return account

    def _credential(self) -> str:
        if self._page is None:
            self.account()
        assert self._page is not None
        return self._page.token

    def _request(self, method: str, path: str, payload: dict[str, str] | None = None) -> dict[str, object]:
        token = self._credential()
        client = http.client.HTTPSConnection('graph.facebook.com', timeout=30)
        try:
            client.request(method, f'/{self.version}/{path}',
                           body=json.dumps(payload).encode() if payload is not None else None,
                           headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
            response = client.getresponse()
            raw = response.read(1024 * 1024 + 1)
            if not 200 <= response.status < 300 or len(raw) > 1024 * 1024:
                raise ValueError('Meta 操作未取得可確認的成功回應')
            result = json.loads(raw)
            if not isinstance(result, dict) or 'error' in result:
                raise ValueError('Meta 操作未取得可確認的成功回應')
            return result
        except (OSError, http.client.HTTPException, ValueError, TypeError):
            raise ValueError('Meta 操作未取得可確認的成功回應') from None
        finally:
            client.close()

    def create(self, caption: str) -> str:
        result = self._request('POST', f'{self.account_id}/media',
                               {'media_type': 'REELS', 'upload_type': 'resumable', 'caption': caption})
        return identifier(result.get('id'))

    def upload(self, container_id: str, stream: BinaryIO, size: int, digest: str) -> None:
        identifier(container_id)
        token = self._credential()
        client = http.client.HTTPSConnection('rupload.facebook.com', timeout=120)
        try:
            client.putrequest('POST', f'/ig-api-upload/{self.version}/{container_id}')
            for key, value in {'Authorization': f'OAuth {token}', 'offset': '0',
                               'file_size': str(size), 'Content-Length': str(size),
                               'Content-Type': 'application/octet-stream'}.items():
                client.putheader(key, value)
            client.endheaders()
            sent, hashed = 0, hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                sent += len(block)
                hashed.update(block)
                client.send(block)
            if sent != size or hashed.hexdigest() != digest:
                raise ValueError('上傳影片內容與核准版本不符')
            response = client.getresponse()
            raw = response.read(65537)
            if not 200 <= response.status < 300 or len(raw) > 65536 or json.loads(raw).get('success') is not True:
                raise ValueError('Meta 未確認影片上傳成功')
        except (OSError, http.client.HTTPException, ValueError, TypeError, AttributeError):
            raise ValueError('Meta 未確認核准影片完整上傳，停止正式發佈') from None
        finally:
            client.close()

    def status(self, container_id: str) -> str:
        result = self._request('GET', f'{identifier(container_id)}?fields=status_code')
        status = result.get('status_code')
        if status not in ('IN_PROGRESS', 'FINISHED', 'ERROR', 'EXPIRED', 'PUBLISHED'):
            raise ValueError('Meta 未回傳可核對的媒體處理狀態')
        return str(status)

    def publish(self, container_id: str) -> str:
        result = self._request('POST', f'{self.account_id}/media_publish',
                               {'creation_id': identifier(container_id)})
        return identifier(result.get('id'))

    def permalink(self, media_id: str) -> str | None:
        result = self._request('GET', f'{identifier(media_id)}?fields=id,permalink')
        link = result.get('permalink')
        if (result.get('id') == media_id and isinstance(link, str)
                and re.fullmatch(r'https://www\.instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/', link)):
            return link
        return None
