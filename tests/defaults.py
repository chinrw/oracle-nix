"""Check configured defaults at the outgoing API boundary without network access."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

package = Path(sys.argv[1])
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    settings = {'model':'gpt-6-astra','reasoningMode':'pro','reasoningEffort':'high'}
    (root/'config.json').write_text(json.dumps(settings))
    preload = root/'mock.cjs'
    preload.write_text('''
const fs = require('node:fs');
globalThis.fetch = async (url, init) => {
  const body = JSON.parse(init.body);
  fs.writeFileSync(process.env.REQUEST_FILE, JSON.stringify(body));
  return new Response(JSON.stringify({id:'resp_fixture',object:'response',status:'completed',
    model:body.model,reasoning:body.reasoning,output:[{type:'message',role:'assistant',
    content:[{type:'output_text',text:'323',annotations:[]}]}],
    usage:{input_tokens:10,output_tokens:1,total_tokens:11}}),
    {status:200,headers:{'content-type':'application/json'}});
};
''')
    env = {k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','TMPDIR')}
    env.update(ORACLE_HOME_DIR=temporary,OPENAI_API_KEY='fixture-key',NODE_OPTIONS='--require='+str(preload),REQUEST_FILE=str(root/'request.json'))
    for extra, expected in [([], {'mode':'pro','effort':'high'}),
                             (['--reasoning-mode','standard','--reasoning-effort','low'], {'mode':'standard','effort':'low'})]:
        subprocess.run([str(package/'bin/oracle'),'--prompt','Compute seventeen times nineteen.',
                        '--search','off','--wait','--background',*extra],cwd=root,env=env,
                       check=True,capture_output=True,text=True,timeout=30)
        request=json.loads((root/'request.json').read_text())
        assert request['model']=='gpt-6-astra', request
        assert request['reasoning']['mode']==expected['mode'], request
        assert request['reasoning']['effort']==expected['effort'], request
    module=(package/'lib/oracle/node_modules/@steipete/oracle/dist/src/mcp/utils.js').as_uri()
    script = root/'mcp.mjs'
    script.write_text(f"import {{mapConsultToRunOptions}} from {json.dumps(module)};\n"+'''
const config = {model:'gpt-6-astra',reasoningMode:'pro',reasoningEffort:'high'};
const api = mapConsultToRunOptions({prompt:'test',userConfig:config,engine:'api'}).runOptions;
if (api.model !== 'gpt-6-astra' || api.reasoningMode !== 'pro' || api.reasoningEffort !== 'high') throw new Error('MCP defaults missing');
const browser = mapConsultToRunOptions({prompt:'test',userConfig:config,engine:'browser'}).runOptions;
if (browser.reasoningMode !== undefined || browser.reasoningEffort !== undefined) throw new Error('API defaults leaked into browser');
''')
    subprocess.run(['node',str(script)],cwd=root,env=env,check=True,capture_output=True,text=True,timeout=30)
print('CLI on-wire defaults, explicit overrides and MCP/browser defaults passed')
