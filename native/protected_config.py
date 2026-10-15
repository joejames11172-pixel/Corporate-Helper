"""Windows machine enrollment protected by DPAPI; no browser credential storage."""
import ctypes,json,os,pathlib
ROOT=(pathlib.Path(os.environ['PROGRAMDATA']) if os.environ.get('PROGRAMDATA') else pathlib.Path(os.environ.get('ALLUSERSPROFILE',os.path.expanduser('~'))) / 'Application Data') / 'Corporate Helper'
def ensure_dir(path):os.makedirs(str(path),exist_ok=True)
def read_bytes(path):
    with path.open('rb') as f:return f.read()
def read_text(path):return read_bytes(path).decode('utf-8')
def write_bytes(path,raw):
    with path.open('wb') as f:f.write(raw)
def write_text(path,text):write_bytes(path,text.encode('utf-8'))
def dpapi(raw,decrypt=False):
    if os.name!='nt':raise RuntimeError('Windows DPAPI required')
    from ctypes import wintypes
    class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buf=ctypes.create_string_buffer(raw);src=Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));dst=Blob()
    api=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    # Machine scope permits the boot task and local native host to use the same
    # enrollment. Installer ACLs restrict the encrypted file to SYSTEM and owner.
    args=[ctypes.byref(src),None,None,None,None,1 if decrypt else 5,ctypes.byref(dst)]
    if not api(*args):raise ctypes.WinError()
    try:return ctypes.string_at(dst.data,dst.size)
    finally:ctypes.windll.kernel32.LocalFree(dst.data)
def save(config):
    ensure_dir(ROOT)
    raw=dpapi(json.dumps(config,separators=(',',':')).encode())
    p=ROOT/'enrollment.dat';temp=ROOT/'enrollment.tmp';write_bytes(temp,raw);os.replace(str(temp),str(p))
def load():return json.loads(dpapi(read_bytes(ROOT/'enrollment.dat'),True).decode())
