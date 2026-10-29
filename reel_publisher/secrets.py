"""Explicit opt-in runtime secrets; never enumerate a user's saved credentials."""

import os
import subprocess


def runtime_secret(variable: str, *, keychain_service: str | None, account: str) -> str | None:
    value = os.environ.get(variable)
    if value:
        return value
    if not keychain_service:
        return None
    try:
        result = subprocess.run(
            ['security', 'find-generic-password', '-s', keychain_service, '-a', account, '-w'],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('無法讀取明確指定的 Keychain 項目') from None
    if result.returncode or not result.stdout.strip():
        raise ValueError('找不到明確指定的 Keychain 項目，請先完成配置')
    return result.stdout.strip()
