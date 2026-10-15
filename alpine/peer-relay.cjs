'use strict';
const {createHash,randomBytes}=require('node:crypto');
const {rpc}=require('./browser-rpc.cjs');
function peerExchange(bridge,data){
 if(!data||!Object.keys(data).every(k=>['enabled','tabs','requests','captures','peer_guid'].includes(k))||typeof data.peer_guid!=='string'||!/^[a-f0-9-]{36}$/.test(data.peer_guid)||!Array.isArray(data.tabs)||data.tabs.length>10||!Array.isArray(data.requests)||data.requests.length>10||!Array.isArray(data.captures)||data.captures.length>20)throw Error('Invalid peer exchange');
 const sid=createHash('sha256').update('native-peer:'+data.peer_guid).digest('hex').slice(0,48);
 let s=bridge.sessions.get(sid);if(!s){s={key:randomBytes(32),counter:0,tabs:[],expires:bridge.now()+3600000,cache:new Map()};bridge.sessions.set(sid,s);}
 s.expires=bridge.now()+3600000;
 s.tabs=data.enabled?data.tabs.map(t=>{if(!Number.isSafeInteger(t.id)||typeof t.origin!=='string'||!/^https:\/\//.test(t.origin)||t.origin.length>300)throw Error('Invalid tab');return{id:t.id,origin:t.origin};}):[];
 if(!data.enabled){s.cache.clear();for(const [id,q]of bridge.queue)if(q.sid===sid)bridge.queue.delete(id);}
 const capture_acks=[];
 for(const r of data.captures){
  const q=bridge.queue.get(r.id);
  if(q&&q.sid===sid&&r.snapshot&&typeof r.snapshot==='object'&&JSON.stringify(r.snapshot).length<=20000){bridge.queue.delete(r.id);bridge.results.set(r.id,{sid,snapshot:r.snapshot,expires:bridge.now()+60000});}
  capture_acks.push(r.id);
 }
 const results=[];
 for(const row of data.requests){
  if(typeof row.request_id!=='string'||!/^[a-f0-9]{32}$/.test(row.request_id))throw Error('Invalid request ID');
  const value=JSON.stringify(row.rpc);let prior=s.cache.get(row.request_id);
  if(prior&&prior.value!==value)throw Error('Request ID collision');
  if(!prior){if(s.cache.size>=256){const first=s.cache.keys().next().value;s.cache.delete(first);}prior={value,response:rpc(bridge,sid,row.rpc)};s.cache.set(row.request_id,prior);}
  results.push({request_id:row.request_id,response:prior.response});
 }
 return{results,commands:[...bridge.queue.values()].filter(q=>q.sid===sid).map(q=>({id:q.id,op:q.op,tabId:q.tabId})),capture_acks};
}
module.exports={peerExchange};
