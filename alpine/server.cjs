// Prototype: HTTPS only; bind loopback until reviewed and explicitly configured.
const fs = require('node:fs');
const https = require('./transport.cjs');
const {timingSafeEqual} = require('node:crypto');
const {Bridge} = require('./core.cjs');
const {peerExchange} = require('./peer-relay.cjs');
const {rpc:browserRPC} = require('./browser-rpc.cjs');
const configPath = process.argv[2];
if (!configPath) throw Error('Usage: node server.cjs CONFIG.json');
const stat = fs.statSync(configPath);
if (stat.mode & 0o077) throw Error('Configuration must have mode 0600');
const cfg = JSON.parse(fs.readFileSync(configPath, 'utf8'));
if(typeof cfg.identity!=='string'||!cfg.identity||!/^\w{64}$/.test(cfg.operatorToken||'')||!cfg.salt||!cfg.verifier)throw Error('Invalid configuration');
if(cfg.bind&&cfg.bind!=='127.0.0.1')throw Error('Prototype must bind loopback; use an authenticated tunnel');
const bridge = new Bridge(cfg);
const reply = (res, status, obj) => {res.writeHead(status, {'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(obj));};
function operator(req) {
  const given = Buffer.from(req.headers.authorization || ''), wanted = Buffer.from('Bearer ' + cfg.operatorToken);
  if (given.length !== wanted.length || !timingSafeEqual(given, wanted)) throw Error('Unauthorized');
}
const server = https.createServer({key:fs.readFileSync(cfg.tlsKey),cert:fs.readFileSync(cfg.tlsCert),minVersion:'TLSv1.2'}, async (req,res) => {
  try {
    if (req.method === 'GET' && req.url === '/health') return reply(res,200,{ok:true,service:'corporate-helper',version:'0.2.0'});
    if(req.url.startsWith('/admin/')) {
      if(req.socket.remoteAddress!=='127.0.0.1')throw Error('Loopback required');
      operator(req);
      if(req.method!=='GET'||req.url!=='/admin/status')return reply(res,404,{error:'Not found'});
      return reply(res,200,{service:'corporate-helper',version:'0.2.0',browserBroker:true,administration:'read-only',tunnels:'managed by existing external service; migration pending',firewall:'migration pending',windows:'not installed'});
    }
    if(cfg.nativeMasterOnly===true&&req.url.startsWith('/srp/'))return reply(res,403,{error:'Browser pairing disabled; local native helper required'});
    if (req.method !== 'POST' || !['/mcp','/srp/start','/srp/finish','/browser/poll','/browser/result','/browser/revoke','/browser/mcp','/operator/status','/operator/peer','/operator/read','/operator/result'].includes(req.url)) return reply(res,404,{error:'Not found'});
    if (!(req.headers['content-type'] || '').startsWith('application/json')) return reply(res,415,{error:'JSON required'});
    let body = ''; for await (const part of req) {body += part; if(Buffer.byteLength(body)>65536) throw Error('Request too large');}
    const data = JSON.parse(body);
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw Error('Object required');
    let answer;
    if(req.url === '/mcp') {
      operator(req); bridge.cleanup();
      if(data.jsonrpc!=='2.0'||typeof data.method!=='string')throw Error('Invalid RPC');
      if(data.id===undefined){res.writeHead(202);res.end();return;}
      let result;
      if(data.method==='initialize')result={protocolVersion:'2025-03-26',capabilities:{tools:{}},serverInfo:{name:'corporate-helper',version:'0.2.0'},instructions:'Read-only prototype. User must pair locally and explicitly enable a tab. Poll snapshot results by request ID. No credential collection or remote click/type tools.'};
      else if(data.method==='ping')result={};
      else if(data.method==='tools/list')result={tools:[
        {name:'browser_status',description:'List paired sessions and explicitly enabled tab origins.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true}},
        {name:'browser_request_snapshot',description:'Request a redacted diagnostic text snapshot of an explicitly enabled tab. Returns request ID; result may take 30 seconds.',inputSchema:{type:'object',properties:{sid:{type:'string'},tabId:{type:'integer'}},required:['sid','tabId'],additionalProperties:false},annotations:{readOnlyHint:true}},
        {name:'browser_snapshot_result',description:'Read the result for a previously returned diagnostic request ID. Unready results should be checked later.',inputSchema:{type:'object',properties:{id:{type:'string'}},required:['id'],additionalProperties:false},annotations:{readOnlyHint:true}}
      ]};
      else if(data.method==='tools/call'){
        const p=data.params||{},a=p.arguments||{};let out;
        if(p.name==='browser_status'&&Object.keys(a).length===0)out={sessions:[...bridge.sessions].map(([sid,s])=>({sid,expires:s.expires,tabs:s.tabs}))};
        else if(p.name==='browser_request_snapshot'&&Object.keys(a).sort().join(',')==='sid,tabId')out=bridge.enqueue(a.sid,a.tabId);
        else if(p.name==='browser_snapshot_result'&&Object.keys(a).join(',')==='id'){const r=bridge.results.get(a.id);out=r?{ready:true,result:r.snapshot}:{ready:false};}
        else throw Error('Unsupported tool');
        result={content:[{type:'text',text:JSON.stringify(out)}]};
      } else {reply(res,200,{jsonrpc:'2.0',id:data.id,error:{code:-32601,message:'Method not found'}});return;}
      answer={jsonrpc:'2.0',id:data.id,result};
    }
    else if(req.url === '/srp/start') answer=await bridge.start(data.identity);
    else if(req.url === '/srp/finish') answer=await bridge.finish(data.challenge,data.A,data.M1);
    else if(req.url.startsWith('/operator/')) {
      operator(req); bridge.cleanup();
      if(req.url === '/operator/peer') {if(req.socket.remoteAddress!=='127.0.0.1')throw Error('Master local relay only');answer=peerExchange(bridge,data);}
      else if(req.url === '/operator/status') answer={sessions:[...bridge.sessions].map(([sid,s])=>({sid,expires:s.expires,tabs:s.tabs}))};
      else if(req.url === '/operator/read') answer=bridge.enqueue(data.sid,data.tabId);
      else {const result=bridge.results.get(data.id);answer=result?{ready:true,result:result.snapshot}:{ready:false};}
    } else {
      const s=bridge.authenticate(req.headers['x-session'],req.url,Number(req.headers['x-counter']),body,req.headers['x-mac']);
      if(req.url === '/browser/mcp') answer=browserRPC(bridge,req.headers['x-session'],data);
      else if(req.url === '/browser/revoke') {bridge.revoke(req.headers['x-session']);answer={revoked:true};}
      else if(req.url === '/browser/poll') {
        if(!Array.isArray(data.tabs)||data.tabs.length>10) throw Error('Invalid tabs');
        s.tabs=data.tabs.map(t=>{if(!Number.isSafeInteger(t.id)||typeof t.origin!=='string'||!/^https?:\/\//.test(t.origin)||t.origin.length>300)throw Error('Invalid tab');return{id:t.id,origin:t.origin};});
        answer={commands:[...bridge.queue.values()].filter(q=>q.sid===req.headers['x-session']).map(q=>({id:q.id,op:q.op,tabId:q.tabId}))};
      } else {
        const task=bridge.queue.get(data.id);
        if(!task||task.sid!==req.headers['x-session'])throw Error('Unknown task');
        if(typeof data.snapshot!=='object'||JSON.stringify(data.snapshot).length>20000)throw Error('Invalid snapshot');
        bridge.queue.delete(data.id);bridge.results.set(data.id,{sid:task.sid,snapshot:data.snapshot,expires:bridge.now()+60000});answer={accepted:true};
      }
    }
    reply(res,200,answer);
  } catch {reply(res,403,{error:'Request rejected'});}
});
server.requestTimeout=10000;server.headersTimeout=10000;
server.listen(cfg.port||8766,cfg.bind||'127.0.0.1',()=>console.log('SRP diagnostic bridge ready'));
