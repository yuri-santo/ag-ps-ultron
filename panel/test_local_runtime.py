import json,subprocess,unittest
from unittest.mock import patch
import local_runtime
class RuntimeTests(unittest.TestCase):
 def failure(self):return subprocess.CompletedProcess([],1,stdout='Falha Wsl/Service/0x8007274c'.encode('utf-16-le'),stderr=b'')
 def ok(self):return subprocess.CompletedProcess([],0,stdout=b'{"ok":true}',stderr=b'')
 def test_read_query_recovers_from_prelaunch_wsl_connection_failure(self):
  with patch('local_runtime.subprocess.run',side_effect=[self.failure(),self.ok()]) as run:
   self.assertTrue(local_runtime.invoke('hub',{'action':'rag_list'})['ok']);self.assertEqual(run.call_count,2)
 def test_mutating_command_is_never_repeated(self):
  with patch('local_runtime.subprocess.run',return_value=self.failure()) as run:
   with self.assertRaises(subprocess.CalledProcessError):local_runtime.invoke('hub',{'action':'task_create','title':'fixture'})
   self.assertEqual(run.call_count,1)
 def test_panel_rag_query_uses_recovery_path(self):
  import hub_api
  with patch('local_runtime.subprocess.run',side_effect=[self.failure(),self.ok()]) as run:
   self.assertTrue(hub_api.dispatch({'action':'rag_list'})['ok']);self.assertEqual(run.call_count,2)
 def test_real_program_error_is_not_retried(self):
  result=subprocess.CompletedProcess([],1,stdout=b'',stderr=b'Python operation failed')
  with patch('local_runtime.subprocess.run',return_value=result) as run:
   with self.assertRaises(subprocess.CalledProcessError):local_runtime.invoke('status')
   self.assertEqual(run.call_count,1)
 def test_read_timeout_is_not_retried_as_a_known_prelaunch_failure(self):
  with patch('local_runtime.subprocess.run',side_effect=subprocess.TimeoutExpired([],1)) as run:
   with self.assertRaises(subprocess.TimeoutExpired):local_runtime.invoke('hub',{'action':'rag_list'})
   self.assertEqual(run.call_count,1)
if __name__=='__main__':unittest.main()
