'use strict';
const schema=(properties={},required=[])=>({type:'object',properties,required,additionalProperties:false});
const registry=[
 {name:'helper_status',context:'helper',description:'Read installed helper version and this authenticated browser session only.',inputSchema:schema(),example:{}},
 {name:'helper_help',context:'helper',description:'Explain available commands, JSON arguments, permissions and examples. Does not execute them.',inputSchema:schema({context:{type:'string',enum:['helper','browser']},command:{type:'string'}}),example:{command:'browser_request_snapshot'}},
 {name:'browser_status',context:'browser',description:'List tab IDs and origins explicitly enabled in your own authenticated browser session.',inputSchema:schema(),example:{}},
 {name:'browser_request_snapshot',context:'browser',description:'Queue a redacted text capture of a tab enabled in your own browser session. Returns capture ID; poll browser_snapshot_result later.',inputSchema:schema({tabId:{type:'integer'}},['tabId']),example:{tabId:9}},
 {name:'browser_snapshot_result',context:'browser',description:'Read a capture belonging to your own session. ready:false means wait and check again. Results expire after 60 seconds.',inputSchema:schema({id:{type:'string',pattern:'^[a-f0-9]{32}$'}},['id']),example:{id:'0123456789abcdef0123456789abcdef'}}
];
function validate(a,s){
 if(!a||typeof a!=='object'||Array.isArray(a))return false;
 if(Object.keys(a).some(k=>!Object.hasOwn(s.properties,k))||s.required.some(k=>!Object.hasOwn(a,k)))return false;
 return Object.entries(a).every(([k,v])=>{const p=s.properties[k];return (p.type==='integer'?Number.isSafeInteger(v):typeof v===p.type)&&(!p.enum||p.enum.includes(v))&&(!p.pattern||new RegExp(p.pattern).test(v))&&(typeof v!=='string'||v.length<=200);});
}
function rpc(bridge,sid,data){
 const fail=(code,message)=>({jsonrpc:'2.0',id:data?.id??null,error:{code,message}});
 if(!data||data.jsonrpc!=='2.0'||!['string','number'].includes(typeof data.id)||typeof data.method!=='string'||JSON.stringify(data.id).length>100)return fail(-32600,'A JSON-RPC 2.0 request with a bounded ID is required');
 bridge.cleanup();const session=bridge.sessions.get(sid);if(!session)return fail(-32001,'Session expired; pair again');
 const ok=result=>({jsonrpc:'2.0',id:data.id,result});
 if(data.method==='initialize')return ok({protocolVersion:'2025-03-26',capabilities:{tools:{}},serverInfo:{name:'corporate-helper-browser',version:'0.2.0'},instructions:'Session-scoped read-only tools. Call tools/list or helper_help. No shell, file writes or other browser sessions.'});
 if(data.method==='ping')return ok({});
 if(data.method==='tools/list')return ok({tools:registry.map(({name,description,inputSchema})=>({name,description,inputSchema,annotations:{readOnlyHint:true}}))});
 if(data.method!=='tools/call')return fail(-32601,'Method not found');
 const p=data.params;if(!p||typeof p!=='object'||Array.isArray(p)||Object.keys(p).some(k=>!['name','arguments'].includes(k)))return fail(-32602,'Expected name and arguments');
 const tool=registry.find(t=>t.name===p.name);if(!tool)return fail(-32602,'Unknown tool; use tools/list');
 const a=p.arguments??{};if(!validate(a,tool.inputSchema))return fail(-32602,'Arguments do not match inputSchema; call helper_help');
 let out;
 if(tool.name==='helper_status')out={service:'corporate-helper',version:'0.2.0',scope:'paired-browser-session',expires:session.expires,tools:registry.map(t=>t.name)};
 else if(tool.name==='browser_status')out={tabs:session.tabs};
 else if(tool.name==='helper_help'){
  const entries=registry.filter(t=>(!a.context||t.context===a.context)&&(!a.command||t.name===a.command));
  if(!entries.length)return fail(-32602,'Unknown context or command');
  out={contexts:['helper','browser'],commands:entries.map(t=>({...t,permissions:'authenticated own session; enabled tabs only',effects:t.name==='browser_request_snapshot'?'queues a temporary read capture':'read only',request:{jsonrpc:'2.0',id:'example-1',method:'tools/call',params:{name:t.name,arguments:t.name==='browser_request_snapshot'?{tabId:session.tabs[0]?.id??9}:t.example}},successExample:t.name==='browser_request_snapshot'?{id:'0123456789abcdef0123456789abcdef'}:t.name==='browser_snapshot_result'?{ready:false}:{},errorExample:{jsonrpc:'2.0',id:'example-1',error:{code:-32602,message:'Arguments do not match inputSchema; call helper_help'}}}))};
 }else if(tool.name==='browser_request_snapshot'){
  if(!session.tabs.some(t=>t.id===a.tabId))return fail(-32003,'Tab not enabled in this session');
  out=bridge.enqueue(sid,a.tabId);
 }else{
  const r=bridge.results.get(a.id),q=bridge.queue.get(a.id);
  if((r&&r.sid!==sid)||(q&&q.sid!==sid))return fail(-32003,'Capture does not belong to this session');
  out=r?{ready:true,result:r.snapshot}:q?{ready:false}:{ready:false,state:'unknown-or-expired',instruction:'Request a new snapshot'};
 }
 return ok({content:[{type:'text',text:JSON.stringify(out)}],isError:false});
}
module.exports={rpc,registry,validate};
