"""One installation, no address/password fields. Personalized private package."""
import json,os,pathlib,shutil,subprocess,sys,time
from protected_config import ROOT,save,ensure_dir,read_text,write_text
SOURCE=pathlib.Path(__file__).resolve().parent
FILES=['lan_policy.py','helper_wire.py','protected_config.py','peer_service.py','native_host.py','supervise.py']
def run():
    if os.name!='nt':raise RuntimeError('Run this installer on Windows')
    cfg=json.loads(read_text(SOURCE/'bootstrap.json'))
    if cfg.get('role')!='non-master':raise ValueError('Non-master enrollment required')
    ensure_dir(ROOT)
    # Replace inherited ACLs BEFORE writing enrollment secrets or private keys.
    owner=os.environ['USERDOMAIN']+'\\'+os.environ['USERNAME']
    p=subprocess.Popen(['cacls',str(ROOT),'/T','/G',owner+':F','SYSTEM:F'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out,err=p.communicate(b'Y\r\n')
    if p.returncode:raise RuntimeError('Enrollment folder ACL configuration failed')
    for name in FILES:shutil.copyfile(str(SOURCE/name),str(ROOT/name))
    for name in ['ca.crt','peer.crt']:shutil.copyfile(str(SOURCE/name),str(ROOT/name))
    save(cfg)
    launcher=ROOT/'native-host.cmd'
    write_text(launcher,'@echo off\r\n"'+sys.executable+'" -E -s -B "'+str(ROOT/'native_host.py')+'" %*\r\n')
    manifest={'name':'com.corporate.helper','description':'Corporate Helper local bridge','path':str(launcher),'type':'stdio','allowed_origins':cfg['allowed_origins']}
    host=ROOT/'native-host.json';write_text(host,json.dumps(manifest,indent=2))
    import winreg
    for vendor in ['Google\\Chrome','Chromium','Supermium']:
        key=winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,'Software\\'+vendor+'\\NativeMessagingHosts\\com.corporate.helper')
        winreg.SetValueEx(key,'',0,winreg.REG_SZ,str(host));winreg.CloseKey(key)
    # Reapply ACLs to copied files as well; source-folder permissions never carry.
    p=subprocess.Popen(['cacls',str(ROOT),'/T','/G',owner+':F','SYSTEM:F'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    p.communicate(b'Y\r\n')
    if p.returncode:raise RuntimeError('Enrollment ACL verification failed')
    pythonw=pathlib.Path(sys.executable).with_name('pythonw.exe')
    task='"'+str(pythonw if pythonw.exists() else pathlib.Path(sys.executable))+'" -E -s -B "'+str(ROOT/'supervise.py')+'"'
    subprocess.check_call(['schtasks','/Create','/TN','Corporate Helper','/SC','ONSTART','/RU','SYSTEM','/TR',task,'/F'])
    # Narrow OS firewall scope to the LAN from which enrollment was issued.
    import ipaddress
    net=ipaddress.ip_network(cfg['subnet']);subnet=str(net.network_address)+'/'+str(net.netmask)
    for proto,port,name in [('TCP','18766','Corporate Helper master channel'),('UDP','18768','Corporate Helper discovery')]:
        subprocess.check_call(['netsh','firewall','add','portopening','protocol='+proto,'port='+port,'name='+name,'mode=ENABLE','scope=CUSTOM','addresses='+subnet])
    subprocess.check_call(['schtasks','/Run','/TN','Corporate Helper'])
    print('Corporate Helper installed. Boot startup, automatic discovery and protected enrollment configured.')
    print('Open/reload Corporate Extension once. No repeated pairing or password entry is required.')
    # The downloaded archive is private enrollment material. Keep it private;
    # never publish bootstrap.json, enrollment.dat, or private keys to GitHub.
if __name__=='__main__':
    try:run()
    except Exception as e:print('INSTALLATION NOT COMPLETE: '+str(e));sys.exit(1)
