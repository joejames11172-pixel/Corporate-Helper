"""Audited fixed native-helper deployment. Package verified before privileged use."""
import base64,datetime,gzip,hashlib,importlib.util,json,os,pathlib,pwd,shutil,ssl,subprocess,sys,tempfile,time,urllib.request,uuid,zipfile
STAGED=pathlib.Path('/opt/peostectica-projects/corporate-helper-native-package.b64')
EXPECTED='4bf933fa02339e9ea20ec16bf8f953745f3b978f240ea01872e8f2c787d67e66'
BASE=pathlib.Path('/opt/corporate-helper')
DEST='1Q_HHMR9qTM164cfhoO81JdVhyC1-wNgE'
def admin():
 p='/opt/peostectica-founder-admin/admin_helper.py';spec=importlib.util.spec_from_file_location('founder_admin',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def launch():
 if os.geteuid()!=0:raise PermissionError('Founder administration required')
 a=admin();a.trusted(pathlib.Path('/opt/peostectica-drive-runtime-candidate/helper_native_upgrade.py'))
 raw=gzip.decompress(base64.b64decode(STAGED.read_bytes(),validate=True))
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('Staged package mismatch')
 jid=uuid.uuid4().hex;a.receipt(jid,'intent',{'task':'helper_native_upgrade','package_sha256':EXPECTED})
 runner="import sys;sys.path.insert(0,'/opt/peostectica-drive-runtime-candidate');from helper_native_upgrade import worker;worker('"+jid+"')"
 subprocess.Popen(['/usr/bin/python3','-I','-B','-c',runner],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
 return {'status':'SUBMITTED','operation_id':jid,'package_sha256':EXPECTED}

def worker(jid):
 a=admin();lock=None
 for attempt in range(120):
  try:lock=a.operation_lock();break
  except RuntimeError:time.sleep(.5)
 if lock is None:return
 try:
  a.receipt(jid,'started',{'task':'helper_native_upgrade'})
  out=deploy();a.receipt(jid,'result',dict(out,success=True))
 except BaseException as e:
  a.receipt(jid,'result',{'success':False,'error_type':type(e).__name__,'errno':getattr(e,'errno',None),'code_lines':[(r.name,r.lineno) for r in __import__('traceback').extract_tb(e.__traceback__)],'message':str(e)[:1500] if isinstance(e,(RuntimeError,ValueError)) else 'Deployment failed; private diagnostics withheld','reconciliation_required':True})
 finally:lock.close()

def deploy():
 raw=gzip.decompress(base64.b64decode(STAGED.read_bytes(),validate=True))
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('Package hash mismatch')
 files=json.loads(raw);allowed_roots={'native','alpine','extension','tests'}
 for name,text in files.items():
  parts=pathlib.PurePosixPath(name).parts
  if len(parts)<2 or parts[0] not in allowed_roots or '..' in parts or not isinstance(text,str):raise ValueError('Invalid package path')
 def cmd(args,**kw):
  p=subprocess.run(args,capture_output=True,timeout=kw.pop('timeout',60),**kw)
  if p.returncode:raise RuntimeError('Command failed: '+args[0]+' '+p.stdout.decode(errors='replace')[-1200:])
  return p.stdout
 def write(p,raw,mode=0o644):
  if p.is_symlink():raise ValueError('Symlink target')
  tmp=p.with_name(p.name+'.new');tmp.write_bytes(raw);os.chmod(tmp,mode);os.replace(tmp,p)
 native=BASE/'native';native.mkdir(exist_ok=True)
 for name,text in files.items():
  if name.startswith('native/'):
   leaf=pathlib.PurePosixPath(name).name
   if leaf.endswith('.py'):compile(text,leaf,'exec')
   write(native/leaf,text.encode())
 stage=pathlib.Path(tempfile.mkdtemp(prefix='native-preflight-',dir=BASE));stage.chmod(0o755)
 try:
  for p in (BASE/'app').iterdir():
   if p.is_file():shutil.copyfile(p,stage/p.name)
  (stage/'node_modules').symlink_to(BASE/'app/node_modules',target_is_directory=True)
  for name,text in files.items():
   if name.startswith('alpine/'):write(stage/pathlib.PurePosixPath(name).name,text.encode())
  u=pwd.getpwnam('peosrp')
  out=cmd(['/usr/bin/node','--test','test.cjs','https-test.cjs','browser-rpc.test.cjs','peer-relay.test.cjs'],cwd=stage,user=u.pw_uid,group=u.pw_gid,extra_groups=[],timeout=120)
  # Only public source tests; no live credentials are printed by this suite.
 finally:shutil.rmtree(stage)
 master=BASE/'master';master.mkdir(mode=0o700,exist_ok=True)
 from cryptography import x509
 from cryptography.hazmat.primitives import hashes,serialization
 from cryptography.hazmat.primitives.asymmetric import rsa
 from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
 now=datetime.datetime.now(datetime.timezone.utc)
 if (master/'config.json').exists():raise RuntimeError('Native deployment already exists; reconcile instead of re-enrolling')
 def key():return rsa.generate_private_key(public_exponent=65537,key_size=2048)
 def pemkey(k):return k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
 ca_key=key();ca_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Corporate Helper private authority')])
 ca=x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,encipher_only=None,decipher_only=None),critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False).sign(ca_key,hashes.SHA256())
 def certificate(k,name,usage):
  return x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])).issuer_name(ca_name).public_key(k.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=1825)).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=True,data_encipherment=False,key_agreement=False,key_cert_sign=False,crl_sign=False,encipher_only=None,decipher_only=None),critical=True).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False).add_extension(x509.ExtendedKeyUsage([usage]),critical=False).add_extension(x509.SubjectAlternativeName([x509.DNSName(name),x509.DNSName('localhost')]),critical=False).sign(ca_key,hashes.SHA256())
 master_key=key();master_cert=certificate(master_key,'corporate-helper-master',ExtendedKeyUsageOID.CLIENT_AUTH)
 peer_key=key();peer_cert=certificate(peer_key,'corporate-helper-peer',ExtendedKeyUsageOID.SERVER_AUTH)
 certpem=lambda c:c.public_bytes(serialization.Encoding.PEM)
 pin=lambda c:hashlib.sha256(c.public_bytes(serialization.Encoding.DER)).hexdigest()
 device=str(uuid.uuid4());master_pin=pin(master_cert);peer_pin=pin(peer_cert)
 cfg={'role':'master','master_pin':master_pin,'peers':{device:{'pin':peer_pin}}}
 # Private enrollment material is kept out of public source and extension files.
 for name,content in {'ca.crt':certpem(ca),'ca.key':pemkey(ca_key),'master.crt':certpem(master_cert),'master.key':pemkey(master_key),'provision.pending.json':json.dumps(cfg).encode()}.items():write(master/name,content,0o600)
 extension=json.loads(files['extension/manifest.json']);der=base64.b64decode(extension['key']);extension_id=''.join(chr(97+int(n,16)) for n in hashlib.sha256(der).hexdigest()[:32])
 sys.path.insert(0,str(native));from lan_policy import local_interfaces
 face=local_interfaces()[0];subnet=str(face.network)
 bootstrap={'role':'non-master','device_id':device,'master_pin':master_pin,'peer_pin':peer_pin,'peer_key_pem':pemkey(peer_key).decode(),'ipc_key':os.urandom(32).hex(),'enabled':True,'subnet':subnet,'allowed_origins':['chrome-extension://'+extension_id+'/']}
 # Fetch only the official x86 runtime. Bound response; never retry a 404.
 runtime_url='https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi'
 runtime_size=24932352;parts=[]
 for offset in range(0,runtime_size,1024*1024):
  end=min(offset+1024*1024,runtime_size)-1
  for attempt in range(2):
   try:
    req=urllib.request.Request(runtime_url,headers={'Range':'bytes='+str(offset)+'-'+str(end),'Accept-Encoding':'identity'})
    with urllib.request.urlopen(req,timeout=15) as response:
     if response.status!=206 or response.headers.get('Content-Range')!='bytes '+str(offset)+'-'+str(end)+'/'+str(runtime_size):raise ValueError('Official runtime range mismatch')
     part=response.read(end-offset+2)
    if len(part)!=end-offset+1:raise ValueError('Official runtime chunk truncated')
    parts.append(part);break
   except urllib.error.HTTPError as e:
    if e.code==404 or attempt==1 or e.code not in (408,429,500,502,503,504):raise
    time.sleep(1)
   except OSError:
    if attempt==1:raise
    time.sleep(1)
 msi=b''.join(parts)
 if len(msi)!=runtime_size or not msi.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):raise ValueError('Official runtime artifact invalid')
 # Stream the archive directly to Drive: Gateway descendants have a 64 KiB
 # filesystem-write limit. Respect it; do not raise or bypass that limit.
 rclone=['/usr/bin/rclone','--config','/root/.config/rclone/rclone.conf','--drive-root-folder-id',DEST,'--drive-skip-shortcuts','--retries','1','--low-level-retries','1','--contimeout','10s','--timeout','60s']
 upload=subprocess.Popen(rclone+['rcat','peostectica-drive:corporate-helper-windows-automatic.zip'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 class StreamingArchive:
  def __init__(self,stream):self.stream=stream;self.count=0;self.digest=hashlib.sha256()
  def write(self,data):
   view=memoryview(data);sent=0
   while sent<len(view):sent+=self.stream.write(view[sent:sent+32768])
   self.digest.update(data);self.count+=len(data);return len(data)
  def tell(self):return self.count
  def flush(self):self.stream.flush()
 output=StreamingArchive(upload.stdin)
 try:
  with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
   for name,text in files.items():
    if name.startswith('native/') and pathlib.PurePosixPath(name).name!='master_agent.py':z.writestr(pathlib.PurePosixPath(name).name,text)
    if name.startswith('extension/') and not name.startswith('extension/tests/') and pathlib.PurePosixPath(name).name not in ('popup.js','popup.html','style.css','SHA256SUMS.json'):z.writestr('Corporate Extension/'+name[len('extension/'):],text)
   z.writestr('bootstrap.json',json.dumps(bootstrap));z.writestr('ca.crt',certpem(ca));z.writestr('peer.crt',certpem(peer_cert));z.writestr('python-3.4.4.msi',msi)
   z.writestr('START HERE.txt','Run Install.cmd once as the Windows administrator. It installs the helper and boot task with no address or password fields. Then load the included Corporate Extension folder once in Supermium. The extension is enabled automatically and shows Waiting for master until the master opens its LAN-only authenticated connection. Keep this private enrollment package private. It contains this device enrollment. Do not install the same enrollment on multiple computers. Windows Server 2003 native integration must be verified on the actual machine. Existing SSH tunnels are preserved; this helper control channel is master-initiated TLS.\r\n')
  upload.stdin.close();upload.stdin=None
  stdout,stderr=upload.communicate(timeout=180)
  if upload.returncode:raise RuntimeError('Installer stream upload failed; exit '+str(upload.returncode))
 except BaseException:
  upload.kill();upload.wait();raise
 rows=json.loads(cmd(rclone+['lsjson','peostectica-drive:corporate-helper-windows-automatic.zip'],timeout=60))
 if isinstance(rows,dict):rows=[rows]
 if len(rows)!=1 or not rows[0].get('ID'):raise RuntimeError('Uploaded package metadata ambiguous')
 package_id=rows[0]['ID'];package_hash=output.digest.hexdigest()
 # Install verified broker files; retain rollback copies and original tunnel.
 backup=pathlib.Path(tempfile.mkdtemp(prefix='native-broker-backup-',dir=BASE));before={}
 for name,text in files.items():
  if name.startswith('alpine/'):
   leaf=pathlib.PurePosixPath(name).name;p=BASE/'app'/leaf;before[leaf]=p.read_bytes() if p.exists() else None
   if before[leaf] is not None:write(backup/leaf,before[leaf])
 config_path=pathlib.Path('/opt/peostectica-browser-diagnostics/private/config.json');config_owner=config_path.stat();config_before=config_path.read_bytes();broker_cfg=json.loads(config_before);broker_cfg['nativeMasterOnly']=True
 def service(action):cmd(['/sbin/rc-service','corporate-helper',action],timeout=30)
 try:
  service('stop')
  write(config_path,json.dumps(broker_cfg).encode(),0o600);os.chown(config_path,config_owner.st_uid,config_owner.st_gid)
  for name,text in files.items():
   if name.startswith('alpine/'):write(BASE/'app'/pathlib.PurePosixPath(name).name,text.encode())
  service('start')
  context=ssl.create_default_context(cafile='/opt/peostectica-browser-diagnostics/public/Peostectica_localhost.crt')
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
  for i in range(20):
   try:
    with opener.open('https://localhost:18766/health',timeout=3) as r:
     if json.load(r).get('service')=='corporate-helper':break
   except Exception:pass
   if i==19:raise RuntimeError('Broker health failed')
   time.sleep(.25)
 except BaseException:
  try:service('stop')
  except Exception:pass
  write(config_path,config_before,0o600);os.chown(config_path,config_owner.st_uid,config_owner.st_gid)
  for leaf,content in before.items():
   if content is not None:write(BASE/'app'/leaf,content)
   elif (BASE/'app'/leaf).exists():(BASE/'app'/leaf).unlink()
  service('start');raise
 write(master/'config.json',json.dumps(cfg).encode(),0o600)
 init=pathlib.Path('/etc/init.d/corporate-helper-master')
 init.write_text('#!/sbin/openrc-run\ncommand="/usr/bin/python3"\ncommand_args="-E -s -B /opt/corporate-helper/native/master_agent.py"\nsupervisor="supervise-daemon"\nrespawn_delay=30\nrespawn_max=0\nrespawn_period=0\npidfile="/run/corporate-helper-master.pid"\ndepend() {\n need net corporate-helper\n}\n')
 init.chmod(0o755);cmd(['/sbin/rc-update','add','corporate-helper-master','default']);cmd(['/sbin/rc-service','corporate-helper-master','start'])
 return {'installed':True,'master_ip':str(face.ip),'subnet':subnet,'device_id':device,'extension_id':extension_id,'windows_package_id':package_id,'windows_package_sha256':package_hash,'official_python_msi_sha256':hashlib.sha256(msi).hexdigest(),'source_sha256':EXPECTED,'tests':'18 installed broker tests passed; Windows runtime integration pending','windows_installed':False}

def diagnostics():
 out={'config_exists':(BASE/'master/config.json').exists(),'pending_exists':(BASE/'master/provision.pending.json').exists(),'public_cert_exists':(BASE/'master/master.crt').exists()}
 try:
  with urllib.request.urlopen('https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi',timeout=10) as r:
   out['runtime_http']=r.status;out['runtime_prefix']=r.read(8).hex()
 except Exception as e:
  out['runtime_error']=type(e).__name__;out['runtime_http']=getattr(e,'code',None);out['runtime_errno']=getattr(e,'errno',None)
 return out
