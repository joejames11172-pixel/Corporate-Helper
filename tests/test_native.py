import ast,hashlib,io,ipaddress,json,pathlib,struct,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'native'))
from lan_policy import permitted_peer,require_peer,choose_source
from peer_service import PeerState,authorize_master
from native_host import read_frame,write_frame

class NativeTests(unittest.TestCase):
 def setUp(self):self.faces=[ipaddress.ip_interface('10.0.0.195/24')]
 def test_busybox_real_subnet_inventory(self):
  from unittest.mock import patch
  from lan_policy import local_interfaces
  with patch('subprocess.check_output',side_effect=[b'default via 10.0.0.1 dev eth0 metric 202\n10.0.0.0/24 dev eth0 scope link src 10.0.0.195\n',b'2: eth0: UP\n    inet 10.0.0.195/24 brd 10.0.0.255 scope global eth0\n']):
   self.assertEqual(str(local_interfaces()[0]),'10.0.0.195/24')
 def test_actual_subnet_only(self):
  for ip in ['10.0.0.1','10.0.0.254']:self.assertTrue(permitted_peer(ip,self.faces))
  for ip in ['10.0.1.2','192.168.1.2','8.8.8.8','127.0.0.1','10.0.0.195','10.0.0.0','10.0.0.255','::ffff:10.0.0.2','10.0.0.2.example','10.0.0.002','169.254.1.2','224.0.0.1','0.0.0.0']:self.assertFalse(permitted_peer(ip,self.faces),ip)
 def test_policy_checks_before_any_connection(self):
  from unittest.mock import patch
  from helper_wire import post_tls
  with patch('socket.create_connection') as dial:
   with self.assertRaises(PermissionError):post_tls('8.8.8.8',18766,None,'peer','/x',{},'f'*64,self.faces)
   dial.assert_not_called()
  self.assertEqual(choose_source('10.0.0.2',self.faces),'10.0.0.195')
 def test_only_pinned_master_on_lan(self):
  cert=b'master certificate';pin=hashlib.sha256(cert).hexdigest()
  self.assertTrue(authorize_master(cert,'10.0.0.2',self.faces,pin))
  for value,ip in [(b'other peer certificate','10.0.0.2'),(None,'10.0.0.2'),(cert,'10.0.1.2'),(cert,'127.0.0.1')]:
   with self.assertRaises(PermissionError):authorize_master(value,ip,self.faces,pin)
 def test_nonmasters_have_no_lan_connection_initiator(self):
  tree=ast.parse(pathlib.Path(__file__).resolve().parents[1].joinpath('native/peer_service.py').read_text())
  calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
  self.assertNotIn('connect',calls);self.assertNotIn('create_connection',calls)
 def test_role_limited_queues(self):
  s=PeerState({'enabled':True,'device_id':'test'})
  s.local('/local/poll',{'tabs':[{'id':7,'origin':'https://gemini.google.com'}]})
  s.local('/local/request',{'request_id':'a'*32,'rpc':{'jsonrpc':'2.0','id':'one','method':'tools/list'}})
  x=s.exchange({'results':[],'commands':[{'id':'c','op':'read','tabId':7},{'id':'d','op':'read','tabId':8},{'id':'e','op':'shell','tabId':7}],'capture_acks':[]},'10.0.0.195')
  self.assertEqual(len(x['requests']),1);self.assertEqual(list(s.commands),['c'])
  s.local('/local/capture',{'id':'c','snapshot':{'text':'test'}})
  x=s.exchange({'results':[{'request_id':'a'*32,'response':{'result':{}}}],'commands':[],'capture_acks':['c']},'10.0.0.195')
  self.assertTrue(s.local('/local/result',{'request_id':'a'*32})['ready']);self.assertEqual(x['captures'],[])
 def test_native_frame_bounds_and_truncation(self):
  out=io.BytesIO();write_frame(out,{'x':'hello'});out.seek(0);self.assertEqual(read_frame(out),{'x':'hello'})
  for raw in [b'\x01',struct.pack('<I',70000),struct.pack('<I',10)+b'{}']:
   with self.assertRaises(ValueError):read_frame(io.BytesIO(raw))
 def test_request_id_collision(self):
  s=PeerState({'enabled':True});s.local('/local/request',{'request_id':'a'*32,'rpc':{'id':1}})
  with self.assertRaises(ValueError):s.local('/local/request',{'request_id':'a'*32,'rpc':{'id':2}})
 def test_python_34_syntax(self):
  for p in pathlib.Path(__file__).resolve().parents[1].joinpath('native').glob('*.py'):ast.parse(p.read_text(),feature_version=(3,4))
if __name__=='__main__':unittest.main()
