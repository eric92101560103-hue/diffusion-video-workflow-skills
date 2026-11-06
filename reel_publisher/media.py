"""Read-only validation of completed local video files."""

from pathlib import Path
from fractions import Fraction
import math
import json
import subprocess


def inspect_video(path: Path) -> None:
    data = _probe(path)
    streams, metadata = data.get('streams'), data.get('format')
    if not isinstance(streams, list) or not isinstance(metadata, dict):
        raise ValueError('影片資訊無法核對')
    if not any(isinstance(stream, dict) and stream.get('codec_type') == 'video' for stream in streams):
        raise ValueError('檔案沒有影片影像')
    if float(metadata.get('duration', '0')) <= 0:
        raise ValueError('影片長度無效')


def _probe(path: Path) -> dict[str, object]:
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
    if not isinstance(data, dict):
        raise ValueError('影片資訊無法核對')
    return data


def inspect_reel_video(path: Path) -> None:
    """Conservative local checks; Meta still validates GOP/container details remotely."""
    data = _probe(path)
    streams, metadata = data.get('streams'), data.get('format')
    if not isinstance(streams, list) or not isinstance(metadata, dict):
        raise ValueError('影片資訊無法核對')
    videos = [s for s in streams if isinstance(s, dict) and s.get('codec_type') == 'video']
    if len(videos) != 1 or path.suffix.lower() not in ('.mp4', '.mov'):
        raise ValueError('單支測試只接受含一條影像的 MP4／MOV')
    if 'mov' not in str(metadata.get('format_name', '')).split(',') or path.stat().st_size > 300_000_000:
        raise ValueError('Reels 需 MOV／MP4 容器且不超過 300 MB')
    video = videos[0]
    try:
        duration = float(metadata['duration'])
        width, height = int(video['width']), int(video['height'])
        fps = float(Fraction(video['avg_frame_rate']))
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        raise ValueError('影片時長、尺寸或影格資訊無法核對') from None
    if not math.isfinite(duration) or not 3 <= duration <= 900:
        raise ValueError('Reels 影片需介於 3 秒與 15 分鐘')
    if width <= 0 or height <= 0 or width > 1920 or not 0.01 <= width / height <= 10:
        raise ValueError('Reels 水平像素不可超過 1920，且需符合長寬比限制')
    if not 23 <= fps <= 60:
        raise ValueError('Reels 影格速率需介於 23 與 60 FPS')
    if (video.get('codec_name') not in ('h264', 'hevc') or video.get('pix_fmt') not in ('yuv420p', 'yuvj420p')
            or video.get('field_order') not in ('progressive', 'unknown')):
        raise ValueError('Reels 需 H.264／HEVC、4:2:0 及循序式掃描')
    if 'bit_rate' in video and int(video['bit_rate']) > 25_000_000:
        raise ValueError('Reels 影像位元率不可超過 25 Mbps')
    for audio in (s for s in streams if isinstance(s, dict) and s.get('codec_type') == 'audio'):
        if (audio.get('codec_name') != 'aac' or int(audio.get('sample_rate', 0)) not in range(1, 48001)
                or audio.get('channels') not in (1, 2)):
            raise ValueError('Reels 音訊需 AAC、48 kHz 以下及單／雙聲道')
        if int(audio.get('bit_rate', 0)) <= 0 or int(audio['bit_rate']) > 128000:
            raise ValueError('單支測試保守要求可核對且不超過 128 kbps 的音訊；請另存合規副本')
