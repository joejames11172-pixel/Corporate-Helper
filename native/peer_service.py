"""Non-master helper: listens only. It never opens an authenticated LAN connection."""
import hashlib,hmac,json,os,socket,ssl,threading,time,uuid
from protected_config import ROOT,load,save
from lan_policy import local_interfaces,permitted_peer
from helper_wire import read_http,reply_http

def authorize_master(cert,source,interfaces,pin):
    if not permitted_peer(source,interfaces):raise PermissionError('Outside local subnet')
    if not cert or hashlib.sha256(cert).hexdigest()!=pin:raise PermissionError('Only the pinned master may authenticate')
    return True

class PeerState:
    def __init__(self,cfg):
        self.cfg=cfg;self.lock=threading.RLock();self.tabs=[];self.requests={};self.captures={};self.commands={};self.last_master=0;self.master_ip=None;self.nonces={}
    def local(self,path,data):
        with self.lock:
            now=time.time()
            self.requests={k:v for k,v in self.requests.items() if v['expires']>now}
            if path=='/local/status':return {'role':'non-master','device_id':self.cfg['device_id'],'enabled':self.cfg.get('enabled',True),'connected':now-self.last_master<12,'master_ip':self.master_ip}
            if path=='/local/set':
                if set(data)!={'enabled'} or not isinstance(data['enabled'],bool):raise ValueError('Boolean required')
                self.cfg['enabled']=data['enabled'];save(self.cfg)
                if not data['enabled']:self.tabs=[];self.requests.clear();self.commands.clear();self.captures.clear()
                return {'enabled':data['enabled']}
            if not self.cfg.get('enabled',True):raise PermissionError('Helper is off')
            if path=='/local/poll':
                tabs=data.get('tabs')
                if not isinstance(tabs,list) or len(tabs)>10:raise ValueError('Invalid tabs')
                for t in tabs:
                    if set(t)!={'id','origin'} or type(t['id'])!=int or not isinstance(t['origin'],str) or not t['origin'].startswith('https://') or len(t['origin'])>300:raise ValueError('Invalid tab')
                self.tabs=tabs
                return {'commands':list(self.commands.values())}
            if path=='/local/capture':
                key=data.get('id');snapshot=data.get('snapshot')
                if key not in self.commands or not isinstance(snapshot,dict) or len(json.dumps(snapshot))>20000:raise ValueError('Unknown capture')
                self.captures[key]={'id':key,'snapshot':snapshot};self.commands.pop(key,None);return {'accepted':True}
            if path=='/local/request':
                key=data.get('request_id');rpc=data.get('rpc')
                if not isinstance(key,str) or len(key)!=32 or not isinstance(rpc,dict):raise ValueError('Invalid request')
                prior=self.requests.get(key)
                if prior and prior['rpc']!=rpc:raise ValueError('Request ID collision')
                if not prior:
                    if len(self.requests)>=64:raise ValueError('Request queue full')
                    self.requests[key]={'rpc':rpc,'expires':now+60,'response':None}
                return {'accepted':True}
            if path=='/local/result':
                row=self.requests.get(data.get('request_id'))
                return {'ready':row is not None and row['response'] is not None,'response':row['response'] if row else None}
            raise ValueError('Unknown local operation')
    def exchange(self,data,source):
        with self.lock:
            if set(data)!={'results','commands','capture_acks'}:raise ValueError('Invalid exchange')
            if any(not isinstance(data[k],list) or len(data[k])>20 for k in data):raise ValueError('Exchange bound')
            self.last_master=time.time();self.master_ip=source
            for row in data['results']:
                request=self.requests.get(row.get('request_id'))
                if request:request['response']=row.get('response')
            for key in data['capture_acks']:self.captures.pop(key,None)
            if self.cfg.get('enabled',True):
                for cmd in data['commands']:
                    if cmd.get('op')=='read' and any(t['id']==cmd.get('tabId') for t in self.tabs):self.commands[cmd['id']]=cmd
            return {'enabled':self.cfg.get('enabled',True),'tabs':self.tabs,'requests':[{'request_id':k,'rpc':v['rpc']} for k,v in self.requests.items() if v['response'] is None and v['expires']>time.time()][:1],'captures':list(self.captures.values())[:1]}

def serve(cfg):
    state=PeerState(cfg);slots=threading.BoundedSemaphore(8)
    import tempfile
    fd,keypath=tempfile.mkstemp(dir=str(ROOT),prefix='tls-key-')
    try:
        with os.fdopen(fd,'w') as f:f.write(cfg['peer_key_pem'])
        context=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2);context.load_cert_chain(str(ROOT/'peer.crt'),keypath)
    finally:os.unlink(keypath)
    context.set_ecdh_curve('prime256v1');context.load_verify_locations(str(ROOT/'ca.crt'));context.verify_mode=ssl.CERT_OPTIONAL
    def handler(raw,address,local):
        conn=None
        try:
            raw.settimeout(8);conn=context.wrap_socket(raw,server_side=True)
            # Authorize LAN identity before parsing any application request.
            if not local:
                authorize_master(conn.getpeercert(binary_form=True),address[0],local_interfaces(),cfg['master_pin'])
            path,data,headers=read_http(conn)
            if local:
                if address[0]!='127.0.0.1' or not path.startswith('/local/'):raise PermissionError('Local IPC only')
                nonce=headers.get('x-nonce','');stamp=headers.get('x-time','');signature=headers.get('x-mac','')
                body=json.dumps(data,sort_keys=True,separators=(',',':'))
                expected=hmac.new(bytes.fromhex(cfg['ipc_key']),(path+'\n'+stamp+'\n'+nonce+'\n'+body).encode(),hashlib.sha256).hexdigest()
                with state.lock:
                    state.nonces={k:v for k,v in state.nonces.items() if v>time.time()-30}
                    if len(nonce)!=32 or nonce in state.nonces or abs(time.time()-float(stamp))>15 or not hmac.compare_digest(expected,signature):raise PermissionError('IPC proof rejected')
                    if len(state.nonces)>=512:raise PermissionError('IPC rate bound')
                    state.nonces[nonce]=time.time()
                answer=state.local(path,data)
            else:
                if path!='/master/exchange':raise PermissionError('Master exchange only')
                answer=state.exchange(data,address[0])
            reply_http(conn,200,answer)
        except Exception:
            try:
                if conn:reply_http(conn,403,{'error':'Helper request rejected'})
            except Exception:pass
        finally:
            try:(conn or raw).close()
            finally:slots.release()
    def listen(ip,port,local):
        server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);server.bind((ip,port));server.listen(8)
        while True:
            raw,address=server.accept()
            if not slots.acquire(False):raw.close();continue
            t=threading.Thread(target=handler,args=(raw,address,local));t.daemon=True;t.start()
    def readiness():
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('',18768));sock.settimeout(2)
        bound=sorted(str(f.ip) for f in local_interfaces());last_reply=0
        while True:
            try:
                if sorted(str(f.ip) for f in local_interfaces())!=bound:os._exit(75)
                raw,source=sock.recvfrom(2048)
                if len(raw)>1024 or not permitted_peer(source[0],local_interfaces()):continue
                packet=json.loads(raw.decode())
                # Discovery is not authentication. A spoofed beacon grants no
                # access; only the subsequent pinned master TLS proof can do so.
                if packet.get('role')!='master' or packet.get('master_pin')!=cfg['master_pin'] or not state.cfg.get('enabled',True):continue
                if time.monotonic()-last_reply<2:continue
                if not isinstance(packet.get('nonce'),str) or len(packet['nonce'])!=32:continue
                last_reply=time.monotonic()
                ready={'role':'ready','device_id':cfg['device_id'],'nonce':packet.get('nonce')}
                sock.sendto(json.dumps(ready,separators=(',',':')).encode(),source)
            except Exception:continue
    for ip,port,local in [('127.0.0.1',18765,True)]+[(str(f.ip),18766,False) for f in local_interfaces()]:
        t=threading.Thread(target=listen,args=(ip,port,local));t.daemon=True;t.start()
    readiness()
if __name__=='__main__':serve(load())
