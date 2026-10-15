"""LAN-only helper policy. Python 3.4 compatible; no DNS or proxy fallback."""
import ipaddress,json,os,re,socket,struct,subprocess

def local_interfaces():
    if os.name == 'nt':
        import ctypes
        class Row(ctypes.Structure):
            _fields_=[('address',ctypes.c_uint32),('index',ctypes.c_uint32),('mask',ctypes.c_uint32),('broadcast',ctypes.c_uint32),('size',ctypes.c_uint32),('unused',ctypes.c_uint16),('kind',ctypes.c_uint16)]
        size=ctypes.c_uint32(0)
        api=ctypes.windll.iphlpapi.GetIpAddrTable
        if api(None,ctypes.byref(size),False) != 122:raise RuntimeError('Interface inventory failed')
        buf=ctypes.create_string_buffer(size.value)
        if api(buf,ctypes.byref(size),False):raise RuntimeError('Interface inventory failed')
        count=ctypes.cast(buf,ctypes.POINTER(ctypes.c_uint32)).contents.value
        if count>256:raise RuntimeError('Interface inventory bound')
        rows=(Row*count).from_buffer(buf,4)
        pairs=[(socket.inet_ntoa(struct.pack('=I',r.address)),socket.inet_ntoa(struct.pack('=I',r.mask))) for r in rows]
    else:
        # Alpine's BusyBox ip has no JSON option. Parse its bounded numeric
        # route/address output; never infer a subnet from a hostname or /24.
        lines=subprocess.check_output(['/sbin/ip','-4','route','show']).decode().splitlines()
        defaults=[]
        for line in lines:
            fields=line.split()
            if fields and fields[0]=='default' and 'dev' in fields:
                device=fields[fields.index('dev')+1]
                metric=int(fields[fields.index('metric')+1]) if 'metric' in fields else 0
                defaults.append((metric,device))
        if not defaults:raise RuntimeError('No default LAN interface')
        device=sorted(defaults)[0][1]
        raw=subprocess.check_output(['/sbin/ip','-4','addr','show','dev',device]).decode()
        pairs=re.findall(r'\binet ([0-9.]+)/([0-9]{1,2})\b',raw)
    out=[]
    for address,mask in pairs:
        face=ipaddress.ip_interface(address+'/'+mask)
        if face.version==4 and face.ip.is_private and not face.ip.is_loopback and not face.ip.is_link_local and face.network.prefixlen>=16 and face.network.prefixlen<=30:out.append(face)
    if not out:raise RuntimeError('No eligible LAN subnet')
    return out

def permitted_peer(value,interfaces):
    try:
        ip=ipaddress.ip_address(value)
        if str(ip)!=value or ip.version!=4 or not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:return False
        return any(ip in f.network and ip not in (f.ip,f.network.network_address,f.network.broadcast_address) for f in interfaces)
    except (ValueError,TypeError):return False

def require_peer(value,interfaces):
    if not permitted_peer(value,interfaces):raise PermissionError('Helper peer must be a literal IPv4 address on the actual local subnet')
    return value

def choose_source(value,interfaces):
    require_peer(value,interfaces)
    return str(next(f.ip for f in interfaces if ipaddress.ip_address(value) in f.network))
