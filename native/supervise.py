"""Boot task watchdog; one process, retry crashed local listener after 30s."""
import ctypes,os,pathlib,subprocess,sys,time
from lan_policy import local_interfaces
if os.name!='nt':raise SystemExit('Windows watchdog only')
mutex=ctypes.windll.kernel32.CreateMutexW(None,False,'Global\\CorporateHelperPeer')
if not mutex or ctypes.windll.kernel32.GetLastError()==183:raise SystemExit(0)
try:
    base=pathlib.Path(__file__).resolve().parent
    while True:
        try:
            scope=','.join(str(f.network.network_address)+'/'+str(f.network.netmask) for f in local_interfaces())
            for proto,port,name in [('TCP','18766','Corporate Helper master channel'),('UDP','18768','Corporate Helper discovery')]:
                subprocess.check_call(['netsh','firewall','add','portopening','protocol='+proto,'port='+port,'name='+name,'mode=ENABLE','scope=CUSTOM','addresses='+scope],creationflags=0x08000000)
            subprocess.call([sys.executable,'-E','-s','-B',str(base/'peer_service.py')],cwd=str(base),creationflags=0x08000000)
        except Exception:pass
        time.sleep(30)
finally:ctypes.windll.kernel32.CloseHandle(mutex)
