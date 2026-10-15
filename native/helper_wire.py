"""Fixed TLS helper transport. Never follows redirects or uses proxy settings."""
import hashlib,http.client,json,socket,ssl
from lan_policy import choose_source
MAX=65536

class TLSConnection(http.client.HTTPSConnection):
    def __init__(self,host,port,context,server_name,source=None):
        http.client.HTTPSConnection.__init__(self,host,port,timeout=8,context=context)
        self.verified_context=context;self.server_name=server_name;self.source=source
    def connect(self):
        raw=socket.create_connection((self.host,self.port),self.timeout,(self.source,0) if self.source else None)
        try:self.sock=self.verified_context.wrap_socket(raw,server_hostname=self.server_name)
        except BaseException:raw.close();raise

def post_tls(ip,port,context,server_name,path,data,peer_pin,interfaces=None,headers=None):
    source=choose_source(ip,interfaces) if interfaces is not None else None
    c=TLSConnection(ip,port,context,server_name,source)
    try:
        c.connect()
        if hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()!=peer_pin:raise PermissionError('Pinned helper certificate mismatch')
        body=json.dumps(data,separators=(',',':')).encode()
        if len(body)>MAX:raise ValueError('Request bound exceeded')
        h={'Content-Type':'application/json','Connection':'close'};h.update(headers or {})
        c.request('POST',path,body,h);r=c.getresponse()
        if r.status!=200:raise RuntimeError('Helper request rejected: '+str(r.status))
        raw=r.read(MAX+1)
        if len(raw)>MAX:raise ValueError('Response bound exceeded')
        return json.loads(raw.decode())
    finally:c.close()

def read_http(conn):
    raw=b''
    while b'\r\n\r\n' not in raw:
        chunk=conn.recv(4096)
        if not chunk:raise ValueError('Truncated headers')
        raw+=chunk
        if not raw or len(raw)>8192:raise ValueError('Header bound exceeded')
    head,body=raw.split(b'\r\n\r\n',1);lines=head.decode('ascii').split('\r\n');parts=lines.pop(0).split(' ')
    if len(parts)!=3 or parts[0]!='POST' or parts[2]!='HTTP/1.1':raise ValueError('POST required')
    h={}
    for line in lines:
        k,sep,v=line.partition(':');k=k.lower()
        if not sep or k in h:raise ValueError('Duplicate or malformed header')
        h[k]=v.strip()
    if 'transfer-encoding' in h or 'expect' in h or not h.get('content-length','').isdigit():raise ValueError('Fixed body required')
    size=int(h['content-length'])
    if size>MAX:raise ValueError('Body bound exceeded')
    while len(body)<size:
        part=conn.recv(min(4096,size-len(body)))
        if not part:raise ValueError('Truncated body')
        body+=part
    if len(body)!=size:raise ValueError('Pipelining forbidden')
    data=json.loads(body.decode())
    if not isinstance(data,dict):raise ValueError('Object required')
    return parts[1],data,h

def reply_http(conn,code,data):
    raw=json.dumps(data,separators=(',',':')).encode()
    if len(raw)>MAX:raise ValueError('Response bound exceeded')
    conn.sendall(('HTTP/1.1 '+str(code)+' Response\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: '+str(len(raw))+'\r\n\r\n').encode()+raw)
