"""Read-only twin dashboard and deterministic proposal validation, no actuation."""
import argparse, json, math, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

def validate(proposal,assets):
    if not isinstance(proposal,dict): return {'allowed':False,'reason':'object_required'}
    asset=assets.get(proposal.get('asset_id'))
    if asset is None: return {'allowed':False,'reason':'unknown_asset'}
    if proposal.get('operation')!='set_speed': return {'allowed':False,'reason':'operation_not_allowed'}
    value=proposal.get('value'); observed=proposal.get('observed_version')
    if type(value) not in (int,float) or not math.isfinite(value): return {'allowed':False,'reason':'finite_number_required'}
    if type(observed) is not int or observed!=asset['version']: return {'allowed':False,'reason':'stale_state'}
    if asset['interlock']: return {'allowed':False,'reason':'interlock_active'}
    if asset['temperature']>asset['max_temperature']: return {'allowed':False,'reason':'over_temperature'}
    if not 0<=value<=asset['max_speed']: return {'allowed':False,'reason':'speed_out_of_range'}
    return {'allowed':True,'reason':'validated_dry_run','actuated':False,'asset_id':proposal['asset_id'],'proposed_speed':value}

def make_server(assets,port=8080):
    class Handler(BaseHTTPRequestHandler):
        def respond(self,data,status=200,kind='application/json; charset=utf-8'):
            payload=data.encode() if isinstance(data,str) else json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
        def do_GET(self):
            if self.path=='/api/assets': self.respond(assets)
            elif self.path=='/': self.respond(Path(__file__).with_name('index.html').read_text(encoding='utf-8'),kind='text/html; charset=utf-8')
            else: self.respond({'error':'not_found'},404)
        def do_POST(self):
            if self.path!='/api/proposals': self.respond({'error':'not_found'},404); return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4096: raise ValueError('invalid length')
                proposal=json.loads(self.rfile.read(length))
                result=validate(proposal,assets); self.respond(result,200 if result['allowed'] else 422)
            except (ValueError,TypeError): self.respond({'error':'invalid_request'},400)
        def log_message(self,*args): pass
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8080); a=p.parse_args()
    assets=json.loads(Path(__file__).with_name('assets.json').read_text())
    server=make_server(assets,a.port); print(f'Dry-run dashboard: http://127.0.0.1:{server.server_port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
