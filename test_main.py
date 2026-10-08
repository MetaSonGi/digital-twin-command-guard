import importlib.util, json, threading, unittest, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("app",ROOT/"main.py")
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.assets=json.loads((ROOT/'assets.json').read_text())
        self.p={'asset_id':'conveyor-01','operation':'set_speed','value':40,'observed_version':7}
    def test_valid_does_not_actuate(self):
        self.assertTrue(guard.validate(self.p,self.assets)['allowed']); self.assertFalse(guard.validate(self.p,self.assets)['actuated'])
    def test_stale_range_nonfinite_and_interlock(self):
        for change,reason in [({'observed_version':6},'stale_state'),({'value':101},'speed_out_of_range'),({'value':float('nan')},'finite_number_required'),({'asset_id':'robot-01','observed_version':3},'interlock_active')]:
            with self.subTest(reason=reason): self.assertEqual(guard.validate({**self.p,**change},self.assets)['reason'],reason)
    def test_http_routes(self):
        server=guard.make_server(self.assets,0); worker=threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(base+'/api/assets',timeout=3) as r: self.assertIn('conveyor-01',json.load(r))
            with urllib.request.urlopen(base+'/',timeout=3) as r: self.assertIn('text/html',r.headers['Content-Type'])
            req=urllib.request.Request(base+'/api/proposals',data=json.dumps(self.p).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=3) as r: self.assertEqual(json.load(r)['reason'],'validated_dry_run')
            req=urllib.request.Request(base+'/api/proposals',data=b'[]')
            with self.assertRaises(urllib.error.HTTPError) as err: urllib.request.urlopen(req,timeout=3)
            self.assertEqual(err.exception.code,422)
        finally: server.shutdown(); server.server_close(); worker.join()

if __name__=="__main__": unittest.main()
