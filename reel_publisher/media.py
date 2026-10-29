"""Read-only validation of completed local video files."""

from pathlib import Path
import json
import subprocess


def inspect_video(path: Path) -> None:
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('ffprobe 無法執行或檢查逾時') from error
    if result.returncode:
        raise ValueError('影片無法讀取或尚未完成')
    data = json.loads(result.stdout)
    streams = data.get('streams', [])
    if not any(stream.get('codec_type') == 'video' for stream in streams):
        raise ValueError('檔案沒有影片影像')
    if float(data.get('format', {}).get('duration', '0')) <= 0:
        raise ValueError('影片長度無效')
