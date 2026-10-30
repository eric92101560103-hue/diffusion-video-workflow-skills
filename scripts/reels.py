#!/usr/bin/env python3
"""Portable, local-review-only entrypoint; does not require pip installation."""
import json
from pathlib import Path
import sys

if sys.version_info < (3, 11):
    print(json.dumps({'error': '需要 Python 3.11 或更新版本'}, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reel_publisher.cli import main

raise SystemExit(main(local_only=True))
