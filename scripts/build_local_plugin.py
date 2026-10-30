#!/usr/bin/env python3
"""Build an allowlisted, self-contained local marketplace, never install into a live host."""
from pathlib import Path
import argparse
import json
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    name = 'diffusion-reels-local'
    prefix = name + '-marketplace'
    plugin = prefix + '/plugins/' + name
    catalog = {'name': 'diffusion-reels-personal', 'interface': {'displayName': 'Reels 本機工作流程'},
               'plugins': [{'name': name, 'source': {'source': 'local', 'path': './plugins/' + name},
                            'policy': {'installation': 'AVAILABLE'}, 'category': 'Productivity'}]}
    files = [repository / 'plugin.json', repository / 'scripts/reels.py']
    files += sorted((repository / 'reel_publisher').glob('*.py'))
    files += sorted(path for path in (repository / 'skills').rglob('*')
                    if path.is_file() and path.suffix in ('.md', '.json', '.yaml', '.txt', '.tsx'))
    guide = repository / 'docs/runbooks/codex-chat-publishing.md'
    if guide.exists():
        files.append(guide)
    # Exclusive creation prevents accidental replacement of an already reviewed artifact.
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr(prefix + '/.agents/plugins/marketplace.json', json.dumps(catalog, ensure_ascii=False, indent=2))
        for path in files:
            if path.is_symlink():
                raise ValueError('package inputs must be regular files')
            output.write(path, plugin + '/' + path.relative_to(repository).as_posix())
    print(json.dumps({'package': str(args.output), 'installed': False, 'scan_enabled': False}))


if __name__ == '__main__':
    main()
