/* Bounded raw TLS/TCP transport. One HTTP request per connection; no HTTP listener. */
'use strict';
const tls=require('node:tls');
function createServer(options,handler){
 const server=tls.createServer({...options,handshakeTimeout:5000},socket=>{
  socket.setTimeout(10000,()=>socket.destroy());
  const deadline=setTimeout(()=>socket.destroy(),10000);
  socket.once('close',()=>clearTimeout(deadline));
  let pending=Buffer.alloc(0),done=false;
  const reject=()=>{done=true;socket.end('HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Length: 0\r\n\r\n');};
  socket.on('error',()=>{});
  socket.on('data',part=>{
   if(done)return;pending=Buffer.concat([pending,part]);
   if(pending.length>73728)return reject();
   const end=pending.indexOf('\r\n\r\n');if(end<0){if(pending.length>8192)reject();return;}
   if(end>8192)return reject();
   const lines=pending.subarray(0,end).toString('latin1').split('\r\n');
   const m=/^(GET|POST) (\/[A-Za-z0-9/_-]*) HTTP\/1\.[01]$/.exec(lines.shift());if(!m)return reject();
   const headers={};
   for(const line of lines){const h=/^([A-Za-z0-9-]+):[ \t]*([^\r\n]*)$/.exec(line);if(!h)return reject();const k=h[1].toLowerCase();if(Object.hasOwn(headers,k))return reject();headers[k]=h[2].trim();}
   if(!headers.host||headers['transfer-encoding']||headers.expect)return reject();
   const length=headers['content-length']||'0';if(!/^(0|[1-9][0-9]{0,5})$/.test(length)||+length>65536)return reject();
   const required=end+4+(+length);if(pending.length<required)return;if(pending.length!==required)return reject();
   done=true;socket.pause();
   const body=pending.subarray(end+4),req={method:m[1],url:m[2],headers,socket,async *[Symbol.asyncIterator](){yield body;}};
   let status=200,responseHeaders={},sent=false;
   const res={writeHead(code,h={}){status=code;responseHeaders=h;},end(value=''){
    if(sent)return;sent=true;const bytes=Buffer.from(value);const safe=Object.entries(responseHeaders).filter(([k,v])=>/^[A-Za-z0-9-]+$/.test(k)&&!/[\r\n]/.test(String(v)));
    socket.end(`HTTP/1.1 ${status} Response\r\nConnection: close\r\nContent-Length: ${bytes.length}\r\nX-Content-Type-Options: nosniff\r\n${safe.map(([k,v])=>k+': '+v+'\r\n').join('')}\r\n`+bytes.toString());
   }};
   Promise.resolve(handler(req,res)).catch(()=>{if(!sent){res.writeHead(500);res.end('{}');}});
  });
 });
 server.maxConnections=32;
 server.on('tlsClientError',()=>{});
 return server;
}
module.exports={createServer};
