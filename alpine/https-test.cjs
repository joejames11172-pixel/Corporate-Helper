const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),https=require('node:https');
const {spawn,execFileSync}=require('node:child_process');
const {srp,routines,hex,derive,mac}=require('./core.cjs');
test('real HTTPS SRP -> signed tab poll -> MCP snapshot with TLS verification',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'peo-srp-test-'));let proc;
 try{
  const cert=path.join(dir,'cert.pem'),key=path.join(dir,'key.pem');
  execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',cert,'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],{stdio:'ignore'});
  const v=await srp.createVerifierAndSalt(routines,'test','test-password-not-for-production');
  const port=18000+Math.floor(Math.random()*10000),operatorToken='a'.repeat(64);
  const cfg=path.join(dir,'config.json');fs.writeFileSync(cfg,JSON.stringify({identity:'test',salt:hex(v.s),verifier:hex(v.v),operatorToken,tlsCert:cert,tlsKey:key,port}),{mode:0o600});
  proc=spawn(process.execPath,['server.cjs',cfg],{cwd:__dirname,stdio:['ignore','pipe','pipe']});
  await new Promise((ok,no)=>{const t=setTimeout(()=>no(Error('Server startup timeout')),5000);proc.stdout.once('data',()=>{clearTimeout(t);ok();});proc.once('exit',()=>{clearTimeout(t);no(Error('Server exited'));});});
  function post(route,obj,headers={}){return new Promise((ok,no)=>{const req=https.request({hostname:'localhost',port,path:route,method:'POST',ca:fs.readFileSync(cert),headers:{'Content-Type':'application/json',...headers}},res=>{let raw='';res.on('data',x=>raw+=x);res.on('end',()=>ok({status:res.statusCode,data:JSON.parse(raw)}));});req.on('error',no);req.end(JSON.stringify(obj));});}
  assert.equal((await post('/operator/status',{})).status,403);
  const c1=await new srp.SRPClientSession(routines).step1('test','test-password-not-for-production');
  const first=(await post('/srp/start',{identity:'test'})).data;
  const c2=await c1.step2(BigInt('0x'+first.salt),BigInt('0x'+first.B));
  const result=(await post('/srp/finish',{challenge:first.challenge,A:hex(c2.A),M1:hex(c2.M1)})).data;
  await c2.step3(BigInt('0x'+result.M2));const sessionKey=derive(c2.S,result.sid);let counter=0;
  const signed=(route,obj)=>{const count=++counter;return post(route,obj,{'X-Session':result.sid,'X-Counter':String(count),'X-Mac':mac(sessionKey,route,count,JSON.stringify(obj))});};
  assert.equal((await signed('/browser/poll',{tabs:[{id:9,origin:'https://example.org'}]})).status,200);
  const auth={Authorization:'Bearer '+operatorToken};
  const status=await new Promise((ok,no)=>{const req=https.request({hostname:'localhost',port,path:'/admin/status',ca:fs.readFileSync(cert),headers:auth},res=>{let raw='';res.on('data',x=>raw+=x);res.on('end',()=>ok({code:res.statusCode,body:JSON.parse(raw)}));});req.on('error',no);req.end();});
  assert.equal(status.code,200);assert.equal(status.body.service,'corporate-helper');
  assert.equal((await post('/admin/status',{},auth)).status,404);
  assert.equal((await post('/operator/read',{sid:result.sid,tabId:99},auth)).status,403);

  const init=await post('/mcp',{jsonrpc:'2.0',id:1,method:'initialize',params:{}},auth);assert.equal(init.data.result.serverInfo.version,'0.2.0');
  const tools=await post('/mcp',{jsonrpc:'2.0',id:2,method:'tools/list'},auth);assert.equal(tools.data.result.tools.length,3);
  const task=(await post('/operator/read',{sid:result.sid,tabId:9},auth)).data;
  const poll=await signed('/browser/poll',{tabs:[{id:9,origin:'https://example.org'}]});assert.equal(poll.data.commands[0].id,task.id);
  assert.equal((await signed('/browser/result',{id:task.id,snapshot:{text:'Public diagnostic example'}})).status,200);
  const snapshot=await post('/mcp',{jsonrpc:'2.0',id:3,method:'tools/call',params:{name:'browser_snapshot_result',arguments:{id:task.id}}},auth);
  assert.equal(JSON.parse(snapshot.data.result.content[0].text).result.text,'Public diagnostic example');
  assert.equal((await post('/browser/mcp',{jsonrpc:'2.0',id:'bad',method:'tools/list'})).status,403);
  const discovery=await signed('/browser/mcp',{jsonrpc:'2.0',id:'jack-list',method:'tools/list'});
  assert.equal(discovery.data.result.tools.length,5);
  const ownStatus=await signed('/browser/mcp',{jsonrpc:'2.0',id:'jack-status',method:'tools/call',params:{name:'helper_status',arguments:{}}});
  assert.equal(JSON.parse(ownStatus.data.result.content[0].text).version,'0.2.0');
  const denied=await signed('/browser/mcp',{jsonrpc:'2.0',id:'jack-deny',method:'tools/call',params:{name:'browser_request_snapshot',arguments:{tabId:99}}});
  assert.equal(denied.data.error.code,-32003);
  const peer=await post('/operator/peer',{peer_guid:'12345678-1234-4234-8234-123456789abc',enabled:true,tabs:[{id:9,origin:'https://gemini.google.com'}],requests:[{request_id:'b'.repeat(32),rpc:{jsonrpc:'2.0',id:'native-help',method:'tools/list'}}],captures:[]},auth);
  assert.equal(peer.status,200);assert.equal(peer.data.results[0].response.result.tools.length,5);
  await signed('/browser/revoke',{});assert.equal((await signed('/browser/poll',{tabs:[]})).status,403);
 }finally{if(proc){proc.kill('SIGTERM');await new Promise(ok=>{if(proc.exitCode!==null)ok();else proc.once('exit',ok);});}fs.rmSync(dir,{recursive:true,force:true});}
});
