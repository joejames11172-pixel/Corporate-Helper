"""Chrome native host: framed stdio to authenticated loopback IPC, no LAN dial."""
import hashlib,hmac,json,os,ssl,struct,sys,time,uuid
from protected_config import ROOT,load
from helper_wire import post_tls

def read_frame(stream):
    head=stream.read(4)
    if not head:return None
    if len(head)!=4:raise ValueError('Truncated native frame')
    size=struct.unpack('<I',head)[0]
    if not 1<=size<=65536:raise ValueError('Native message bound')
    parts=[];left=size
    while left:
        raw=stream.read(left)
        if not raw:raise ValueError('Truncated native message')
        parts.append(raw);left-=len(raw)
    data=json.loads(b''.join(parts).decode())
    if not isinstance(data,dict):raise ValueError('Object required')
    return data

def write_frame(stream,data):
    raw=json.dumps(data,separators=(',',':')).encode()
    if len(raw)>65536:raise ValueError('Native result bound')
    stream.write(struct.pack('<I',len(raw))+raw);stream.flush()

class LocalClient:
    def __init__(self,cfg):
        self.cfg=cfg;self.context=ssl.create_default_context(cafile=str(ROOT/'ca.crt'))
    def call(self,path,data):
        nonce=uuid.uuid4().hex;stamp=str(time.time());body=json.dumps(data,sort_keys=True,separators=(',',':'))
        proof=hmac.new(bytes.fromhex(self.cfg['ipc_key']),(path+'\n'+stamp+'\n'+nonce+'\n'+body).encode(),hashlib.sha256).hexdigest()
        return post_tls('127.0.0.1',18765,self.context,'localhost',path,data,self.cfg['peer_pin'],headers={'X-Nonce':nonce,'X-Time':stamp,'X-Mac':proof})
    def handle(self,m):
        op=m.get('op');data=m.get('data',{})
        if op=='status':return self.call('/local/status',{})
        if op=='set':return self.call('/local/set',data)
        if op=='poll':return self.call('/local/poll',data)
        if op=='capture':return self.call('/local/capture',data)
        if op!='rpc' or not isinstance(data,dict):raise ValueError('Unsupported native operation')
        request_id=uuid.uuid4().hex
        self.call('/local/request',{'request_id':request_id,'rpc':data})
        until=time.monotonic()+18
        while time.monotonic()<until:
            result=self.call('/local/result',{'request_id':request_id})
            if result['ready']:return result['response']
            time.sleep(0.25)
        raise RuntimeError('Master has not returned this request; no automatic request replay')

def main():
    cfg=load()
    if len(sys.argv)<2 or sys.argv[1] not in cfg['allowed_origins']:raise PermissionError('Unregistered extension origin')
    if os.name=='nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(),os.O_BINARY);msvcrt.setmode(sys.stdout.fileno(),os.O_BINARY)
    client=LocalClient(cfg)
    while True:
        packet=read_frame(sys.stdin.buffer)
        if packet is None:break
        ident=packet.get('id')
        try:out={'id':ident,'ok':True,'result':client.handle(packet)}
        except Exception as e:out={'id':ident,'ok':False,'error':str(e) if isinstance(e,(ValueError,RuntimeError,PermissionError)) else 'Local helper unavailable'}
        write_frame(sys.stdout.buffer,out)
if __name__=='__main__':main()
