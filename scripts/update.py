#!/usr/bin/env python3
"""Resolve a stable npm release and update its lock and Nix hash together."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '@steipete/oracle'
REGISTRY = 'https://registry.npmjs.org/'


def command(arguments, cwd=None):
    result = subprocess.run(arguments, cwd=cwd, check=True, stdout=subprocess.PIPE,
                            stderr=sys.stderr, text=True, timeout=300)
    return result.stdout.strip()


def stable_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Expected a stable npm version in major.minor.patch form')
    return value


def update(root, target=None, check=False, refresh=False):
    directory = root / 'package'
    manifest = json.loads((directory / 'package.json').read_text())
    current = stable_version(manifest['version'])
    if manifest['dependencies'][PACKAGE] != current:
        raise ValueError('Manifest version and Oracle dependency disagree')
    version = stable_version(target) if target else stable_version(json.loads(command([
        'npm', 'view', PACKAGE, 'version', '--json', '--registry='+REGISTRY,
        '--fetch-retries=0', '--fetch-timeout=15000',
    ])))
    result = {'current': current, 'version': version, 'update_available': version != current, 'changed': False}
    if check or (version == current and not refresh):
        return result
    with tempfile.TemporaryDirectory(prefix='oracle-nix-update-') as temporary:
        candidate = Path(temporary)
        manifest['version'] = version
        manifest['dependencies'][PACKAGE] = version
        manifest_text = json.dumps(manifest, indent=2) + '\n'
        (candidate / 'package.json').write_text(manifest_text)
        (candidate / 'package-lock.json').write_bytes((directory / 'package-lock.json').read_bytes())
        command(['npm','install','--package-lock-only','--ignore-scripts','--no-audit','--no-fund',
                 '--registry='+REGISTRY,'--fetch-retries=0','--fetch-timeout=15000'],cwd=candidate)
        lock_text = (candidate / 'package-lock.json').read_text()
        lock = json.loads(lock_text)
        resolved = lock['packages']['node_modules/'+PACKAGE]
        if lock['version'] != version or resolved['version'] != version or not resolved.get('integrity'):
            raise ValueError('Resolved npm lock does not match the requested release')
        deps_hash = command(['prefetch-npm-deps',str(candidate/'package-lock.json')])
        if not re.fullmatch(r'sha256-[A-Za-z0-9+/]{43}=', deps_hash):
            raise ValueError('prefetch-npm-deps returned an invalid hash')
        # Do not replace repository files until both resolution and hashing succeeded.
        for name, content in [('package.json',manifest_text),('package-lock.json',lock_text),('npm-deps-hash',deps_hash+'\n')]:
            destination = directory / name
            if destination.read_text() != content:
                result['changed'] = True
            destination.write_text(content)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', help='Use a specific stable release instead of npm latest')
    parser.add_argument('--check', action='store_true', help='Read metadata without changing files')
    parser.add_argument('--refresh', action='store_true', help='Resolve and hash even if the version is unchanged')
    args = parser.parse_args()
    print(json.dumps(update(ROOT,args.version,args.check,args.refresh)))


if __name__ == '__main__':
    main()
