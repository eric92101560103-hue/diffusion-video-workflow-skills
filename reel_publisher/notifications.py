"""Email is an external boundary; credentials are supplied only at runtime."""

from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol
import os
import smtplib
import ssl

from .secrets import runtime_secret


@dataclass(frozen=True)
class Notice:
    candidate_id: str
    filename: str


@dataclass(frozen=True)
class NoticeStatus:
    candidate_id: str
    status: str


class Notifier(Protocol):
    def send(self, notice: Notice) -> None: ...


@dataclass(frozen=True)
class SMTPNotifier:
    host: str
    port: int
    sender: str
    recipient: str
    username: str | None = None
    password: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls) -> 'SMTPNotifier':
        names = ['REEL_SMTP_HOST', 'REEL_EMAIL_FROM', 'REEL_EMAIL_TO']
        if any(not os.environ.get(name) for name in names):
            raise ValueError('請先設定 SMTP 主機、寄件與收件地址；尚未寄送通知')
        username = os.environ.get('REEL_SMTP_USERNAME')
        password = runtime_secret('REEL_SMTP_PASSWORD',
                                  keychain_service=os.environ.get('REEL_SMTP_KEYCHAIN_SERVICE'),
                                  account=username or '')
        if bool(username) != bool(password):
            raise ValueError('SMTP 使用者名稱與密碼須一起設定')
        port = int(os.environ.get('REEL_SMTP_PORT', '465'))
        if not 1 <= port <= 65535:
            raise ValueError('SMTP 連線埠無效')
        return cls(os.environ[names[0]], port, os.environ[names[1]], os.environ[names[2]], username, password)

    def send(self, notice: Notice) -> None:
        message = EmailMessage()
        message['From'] = self.sender
        message['To'] = self.recipient
        message['Subject'] = f'Reels 待審核：{Path(notice.filename).name}'
        message['Message-ID'] = f'<reel-review-{notice.candidate_id}@reel-publisher.local>'
        message.set_content(
            '發現新的待發佈影片，尚未啟用發佈。\n'
            f'影片：{Path(notice.filename).name}\n候選 ID：{notice.candidate_id}\n'
            '請回到 Codex 的剪輯專案對話，填寫文案、確認順序與日期。\n'
            '你核准後才會進入後續上傳及雲端啟用流程。\n'
        )
        with smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=30) as client:
            if self.username and self.password:
                client.login(self.username, self.password)
            client.send_message(message)
