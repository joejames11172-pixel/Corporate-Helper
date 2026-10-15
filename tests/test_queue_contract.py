import importlib.util,pathlib,unittest
from datetime import datetime,timezone
spec=importlib.util.spec_from_file_location('q',pathlib.Path(__file__).parents[1]/'shared/queue_contract.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
G='11111111-1111-4111-8111-111111111111';R='22222222-2222-4222-8222-222222222222'
class Rules(unittest.TestCase):
 def packet(self): return {'protocol':q.PROTOCOL,'request_id':R,'tool':'sms.enqueue','arguments':{'recipient':'Example contact','text':'Example text'}}
 def test_identity_bound_to_principal(self):
  p=self.packet();self.assertEqual(q.validate_request(p,G)['worker_guid'],G)
  p['worker_guid']=R
  with self.assertRaises(ValueError):q.validate_request(p,G)
 def test_unknown_tool(self):
  p=self.packet();p['tool']='shell'
  with self.assertRaises(ValueError):q.validate_request(p,G)
 def test_header_injection(self):
  p=self.packet();p['arguments']['recipient']='Example\r\nBcc: other'
  with self.assertRaises(ValueError):q.validate_request(p,G)
 def test_txt_email(self):
  name,raw=q.mail_record(q.validate_request(self.packet(),G),datetime.now(timezone.utc),'recipient@example.net','example.org')
  self.assertIn('.(out).'+G+'.txt',name);self.assertIn((G+'.sms@example.org').encode(),raw)
  self.assertIn(b'X-Queue-State: QUEUED',raw)
 def test_order(self):
  a=q.queue_name(datetime(2026,1,1,tzinfo=timezone.utc),'in',G)
  b=q.queue_name(datetime(2026,1,2,tzinfo=timezone.utc),'in',G)
  self.assertLess(a,b)
 def test_objectives(self):
  self.assertFalse(q.requires_objectives('_readme.txt','any','queue'))
  self.assertFalse(q.requires_objectives('message.txt','queue','queue'))
  self.assertTrue(q.requires_objectives('message.txt','other','queue'))
 def test_unknown_never_replayed(self):
  self.assertEqual(q.handoff_decision('a','b','v1','v1',False,'UNKNOWN',True),'RECONCILE_ONLY')
 def test_fallback_requires_exact_release_and_lease(self):
  self.assertEqual(q.handoff_decision('a','b','v1','v1',False,'NOT_ACCEPTED',True),'FALLBACK_EXECUTE')
  self.assertEqual(q.handoff_decision('a','b','v2','v1',False,'NEW',True),'QUEUE_PENDING')
  self.assertEqual(q.handoff_decision('a','b','v1','v1',False,'NEW',False),'QUEUE_PENDING')
 def test_hostname_is_not_master_identity(self):
  self.assertEqual(q.handoff_decision('b','b','v1','v1',False,'NEW'),'QUEUE_PENDING')
 def test_reply(self):
  self.assertEqual(q.inbound_route(G+'.sms@example.org','example.org',{G:'registered-session'})['route'],'registered-session')
  with self.assertRaises(ValueError):q.inbound_route(R+'.sms@example.org','example.org',{G:'session'})
if __name__=='__main__':unittest.main()
