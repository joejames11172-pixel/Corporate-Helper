"""Only master dials peers. Actual subnet checked before TCP and authentication."""
import hashlib,json,os,pathlib,socket,ssl,threading,time,uuid,urllib.request
from lan_policy import local_interfaces,require_peer
from helper_wire import post_tls
BASE=pathlib.Path('/opt/corporate-helper/master')

def operator_call(cfg,data):
    context=ssl.create_default_context(cafile=cfg['tlsCert'])
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
    body=json.dumps(data,separators=(',',':')).encode()
    req=urllib.request.Request('https://localhost:18766/operator/peer',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+cfg['operatorToken']})
    with opener.open(req,timeout=8) as r:
        raw=r.read(65537)
        if len(raw)>65536:raise ValueError('Operator result bound')
        return json.loads(raw.decode())

def run():
    cfg=json.loads((BASE/'config.json').read_text())
    if cfg.get('role')!='master':raise PermissionError('Only master may initiate connections')
    broker=json.loads(pathlib.Path('/opt/peostectica-browser-diagnostics/private/config.json').read_text())
    context=ssl.create_default_context(cafile=str(BASE/'ca.crt'));context.load_cert_chain(str(BASE/'master.crt'),str(BASE/'master.key'))
    faces=local_interfaces();sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);sock.bind((str(faces[0].ip),18768));sock.settimeout(1)
    allowed=cfg['peers'];active={};nonces={};lock=threading.Lock()
    def worker(device,ip):
        delivery={'results':[],'commands':[],'capture_acks':[]};last_success=time.monotonic()
        try:
            while True:
                # Re-evaluate actual local routing on EVERY reconnect/exchange.
                current=local_interfaces();require_peer(ip,current)
                try:
                    answer=post_tls(ip,18766,context,'corporate-helper-peer','/master/exchange',delivery,allowed[device]['pin'],current)
                    if not isinstance(answer,dict) or set(answer)!={'enabled','tabs','requests','captures'}:raise ValueError('Invalid peer response')
                    delivery=operator_call(broker,dict(answer,peer_guid=device))
                    if not answer['enabled']:return
                    last_success=time.monotonic()
                    time.sleep(1)
                except Exception:
                    if time.monotonic()-last_success>35:return
                    # Failed exchanges are retried only by the master, at 30s.
                    time.sleep(30)
        finally:
            with lock:active.pop(device,None)
    last=0;bound=sorted(str(f.ip) for f in faces)
    while True:
        if sorted(str(f.ip) for f in local_interfaces())!=bound:return
        now=time.monotonic()
        if now-last>=5:
            faces=local_interfaces();nonce=uuid.uuid4().hex;nonces={k:v for k,v in nonces.items() if v>now-30};nonces[nonce]=now
            beacon={'role':'master','master_pin':cfg['master_pin'],'nonce':nonce,'time':time.time()}
            raw=json.dumps(beacon,separators=(',',':')).encode()
            for f in faces:sock.sendto(raw,(str(f.network.broadcast_address),18768))
            last=now
        try:
            raw,source=sock.recvfrom(2048)
            require_peer(source[0],local_interfaces())
            if len(raw)>1024:continue
            packet=json.loads(raw.decode());device=packet.get('device_id')
            if packet.get('role')!='ready' or packet.get('nonce') not in nonces or device not in allowed:continue
            with lock:
                if device in active:continue
                t=threading.Thread(target=worker,args=(device,source[0]));t.daemon=True;active[device]=t;t.start()
        except (socket.timeout,ValueError,PermissionError):continue
if __name__=='__main__':run()
