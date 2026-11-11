"""Check packaged CLI and MCP without credentials, network or a browser."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time


def main(package, version):
    with tempfile.TemporaryDirectory(prefix='oracle-nix-check-') as temporary:
        root = Path(temporary)
        env = {key:value for key,value in os.environ.items() if key in ('PATH','HOME','LANG','TMPDIR')}
        env['ORACLE_HOME_DIR'] = temporary
        binary = str(package / 'bin/oracle')
        def cli(*args):
            return subprocess.run([binary,*args],cwd=root,env=env,check=True,capture_output=True,text=True,timeout=30).stdout
        assert cli('--version').strip() == version
        assert '--help' in cli('--help')
        (root/'sample.js').write_text('const answer = 42;\n')
        assert 'const answer = 42;' in cli('--render','--file','sample.js','--prompt','Explain this sample.')
        cli('--engine','api','--model','gpt-6-astra','--reasoning-mode','pro','--reasoning-effort','high',
            '--dry-run','summary','--prompt','Explain this sample.','--file','sample.js')
        with (root/'mcp.stderr').open('wb') as log:
            process = subprocess.Popen([str(package/'bin/oracle-mcp')],cwd=root,env=env,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            pending = b''
            def send(data):
                process.stdin.write((json.dumps(data)+'\n').encode())
                process.stdin.flush()
            def receive(identity):
                nonlocal pending
                deadline = time.monotonic()+15
                while time.monotonic() < deadline:
                    while b'\n' in pending:
                        line,pending = pending.split(b'\n',1)
                        if not line:
                            continue
                        message = json.loads(line)
                        if message.get('id') == identity:
                            assert 'error' not in message, message
                            return message['result']
                    if selector.select(max(0,deadline-time.monotonic())):
                        chunk = os.read(process.stdout.fileno(),65536)
                        if not chunk:
                            raise RuntimeError('MCP exited before its response')
                        pending += chunk
                raise TimeoutError('MCP response timed out')
            try:
                send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{
                    'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'oracle-nix-check','version':'1'}}})
                assert 'tools' in receive(1)['capabilities']
                send({'jsonrpc':'2.0','method':'notifications/initialized'})
                send({'jsonrpc':'2.0','id':2,'method':'tools/list'})
                names = {tool['name'] for tool in receive(2)['tools']}
                assert {'consult','sessions','wait'} <= names, names
                send({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'sessions','arguments':{'limit':1}}})
                assert not receive(3).get('isError',False)
            finally:
                selector.close()
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                process.stdout.close()
        print('CLI version, render, API parameter preview and MCP checks passed')


if __name__ == '__main__':
    main(Path(sys.argv[1]),sys.argv[2])
