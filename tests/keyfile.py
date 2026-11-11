"""Verify runtime key-file loading in the installed entrypoints using fake keys."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main(package):
    key_path = Path('/tmp/oracle-nix-keyfile-check')
    if key_path.exists():
        raise RuntimeError('Key-file test path is already occupied')
    with tempfile.TemporaryDirectory(prefix='oracle-keyfile-') as temporary:
        root = Path(temporary)
        preload = root/'verify.cjs'
        preload.write_text('if (process.env.OPENAI_API_KEY !== process.env.EXPECTED_KEY) throw new Error("Wrong runtime credential source");\n')
        env = {k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','TMPDIR')}
        env.update(ORACLE_HOME_DIR=temporary,NODE_OPTIONS='--require='+str(preload))
        try:
            key_path.write_text('file-fixture-key\n')
            key_path.chmod(0o600)
            for name in ('oracle','oracle-mcp'):
                command = [str(package/'bin'/name)] + (['--version'] if name == 'oracle' else [])
                for overrides in ({'EXPECTED_KEY':'file-fixture-key'}, {'OPENAI_API_KEY':'caller-fixture-key','EXPECTED_KEY':'caller-fixture-key'}):
                    subprocess.run(command,cwd=root,env=env|overrides,input='',capture_output=True,text=True,check=True,timeout=15)
            key_path.unlink()
            # A missing optional key must not prevent help or browser-only startup.
            subprocess.run([str(package/'bin/oracle'),'--version'],cwd=root,env=env,input='',capture_output=True,text=True,check=True,timeout=15)
        finally:
            key_path.unlink(missing_ok=True)
    print('Both entrypoints load the runtime file, preserve explicit keys and tolerate a missing optional file')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
