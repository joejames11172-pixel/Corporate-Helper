const {test}=require('node:test');
const assert=require('node:assert/strict');
const {srp,routines,hex,derive,mac,Bridge}=require('./core.cjs');
const I='test-device',P='test-only-long-pairing-password';
async function fixture(){const v=await srp.createVerifierAndSalt(routines,I,P);const b=new Bridge({identity:I,salt:hex(v.s),verifier:hex(v.v)});const c1=await new srp.SRPClientSession(routines).step1(I,P);const start=await b.start(I);const c2=await c1.step2(BigInt('0x'+start.salt),BigInt('0x'+start.B));return{b,c2,start};}
async function login(){const x=await fixture();x.result=await x.b.finish(x.start.challenge,hex(x.c2.A),hex(x.c2.M1));await x.c2.step3(BigInt('0x'+x.result.M2));x.key=derive(x.c2.S,x.result.sid);return x;}
test('mutual SRP proofs and equal derived keys',async()=>{const x=await login();assert.deepEqual(x.key,x.b.sessions.get(x.result.sid).key);});
test('incorrect password rejected; challenge consumed',async()=>{const x=await fixture();const c=await new srp.SRPClientSession(routines).step1(I,'incorrect-long-password');const bad=await c.step2(BigInt('0x'+x.start.salt),BigInt('0x'+x.start.B));await assert.rejects(x.b.finish(x.start.challenge,hex(bad.A),hex(bad.M1)));await assert.rejects(x.b.finish(x.start.challenge,hex(x.c2.A),hex(x.c2.M1)));});
test('invalid A rejected',async()=>{const x=await fixture();await assert.rejects(x.b.finish(x.start.challenge,'0',hex(x.c2.M1)));});
test('invalid B rejected by client',async()=>{const c=await new srp.SRPClientSession(routines).step1(I,P);await assert.rejects(c.step2(1n,0n));});
test('forged server proof rejected',async()=>{const x=await fixture();await assert.rejects(x.c2.step3(1n));});
test('authentication proof cannot replay',async()=>{const x=await login();await assert.rejects(x.b.finish(x.start.challenge,hex(x.c2.A),hex(x.c2.M1)));});
test('signed request replay and cross-route use rejected',async()=>{const x=await login(),body='{"tabs":[]}';const sig=mac(x.key,'/browser/poll',1,body);x.b.authenticate(x.result.sid,'/browser/poll',1,body,sig);assert.throws(()=>x.b.authenticate(x.result.sid,'/browser/poll',1,body,sig));assert.throws(()=>x.b.authenticate(x.result.sid,'/browser/result',2,body,sig));});
test('modified payload rejected without advancing counter',async()=>{const x=await login();const sig=mac(x.key,'/browser/poll',1,'{}');assert.throws(()=>x.b.authenticate(x.result.sid,'/browser/poll',1,'{"x":1}',sig));assert.equal(x.b.sessions.get(x.result.sid).counter,0);});
test('unenrolled tab denied; enabled tab queues only read',async()=>{const x=await login();assert.throws(()=>x.b.enqueue(x.result.sid,123));x.b.sessions.get(x.result.sid).tabs=[{id:123,origin:'https://example.org'}];const q=x.b.enqueue(x.result.sid,123);assert.equal(x.b.queue.get(q.id).op,'read');});
test('revoke clears commands and rejects further requests',async()=>{const x=await login();x.b.sessions.get(x.result.sid).tabs=[{id:1,origin:'https://example.org'}];x.b.enqueue(x.result.sid,1);x.b.revoke(x.result.sid);assert.equal(x.b.queue.size,0);assert.throws(()=>x.b.authenticate(x.result.sid,'/browser/poll',1,'{}',mac(x.key,'/browser/poll',1,'{}')));});
test('expired session rejected',async()=>{const x=await login();x.b.now=()=>Date.now()+3600001;assert.throws(()=>x.b.authenticate(x.result.sid,'/browser/poll',1,'{}',mac(x.key,'/browser/poll',1,'{}')));});
test('unknown identity and excess attempts rejected',async()=>{const x=await fixture();for(let i=0;i<4;i++)await assert.rejects(x.b.start('unknown'));await assert.rejects(x.b.start(I),/rate limit/);});
