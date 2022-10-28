from os import environ
configPath=environ.get('SSER_CONFIG_PATH','sser.ini')
print('configPath =',configPath)
from configparser import ConfigParser
config=ConfigParser()
try:
    with open(configPath,'r') as configFile:
        config.read_file(configFile)
except:
    print('error reading config, creating default')
    with open(configPath,'w') as configFile:
        config['NETWORK']={
            'IP':'localhost',
            'Port':4000
        }
        config['LOG']={
            'message':False
        }
        config.write(configFile)

print('config loaded, initializing server')

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
pathFunctions={} # Dict{requestlineregex:function}
sseClients={} # dict[path]=list[bytesio]
class ServerSentEventsRelay(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,format,*args):
        print(format % args)
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin','*')
        super().end_headers()
    def do_DISPATCH(self):
        from re import match
        for requestline, function in pathFunctions.items():
            if(match(requestline,self.requestline)):
                return function(self)!=False
        return False
    def do_GET(self):
        self.do_DISPATCH() or super().do_GET()
    def do_HEAD(self):
        self.do_DISPATCH() or super().do_HEAD()
    def do_POST(self):
        self.do_DISPATCH()
    def do_PUT(self):
        self.do_DISPATCH()
    def do_DELETE(self):
        self.do_DISPATCH()
    def do_OPTIONS(self):
        self.do_DISPATCH()
def sseSend(path:str,message:str,event:str=None,id:str=None):
    if(path not in sseClients):
        return False
    if(len(sseClients[path])==0):
        return False
    sent=False
    for wfile in sseClients[path]:
        if wfile.closed:
            continue
        if id:
            wfile.write(('id: '+id+'\n').encode())
        if event:
            wfile.write(('event: '+event+'\n').encode())
        for part in message.split('\n'):
            wfile.write(('data: '+part+'\n').encode())
        wfile.write('\n'.encode())
        wfile.flush()
        sent=True
    return sent
def sseGet(request:ServerSentEventsRelay):
    if request.path not in sseClients:
        sseClients[request.path]=[]
    sseClients[request.path].append(request.wfile)
    request.send_response(200)
    request.send_header('Content-Type','text/event-stream')
    request.end_headers()
def ssePost(request:ServerSentEventsRelay):
    message=request.rfile.read(int(request.headers['Content-Length'])).decode()
    event=request.headers['event']
    id=request.headers['id']
    if not sseSend(request.path,message,event,id):
        request.send_error(404)
    else:
        request.send_response(204)
        if(config['LOG']['message']):
            print({'path':request.path,'event':event,'message':message,'id':id})
    request.end_headers()
def sseOptions(request:ServerSentEventsRelay):
    request.send_response(204)
    request.send_header('Access-Control-Allow-Headers', 'event,id')
    request.end_headers()
pathFunctions['GET /']=sseGet
pathFunctions['POST /']=ssePost
pathFunctions['OPTIONS /']=sseOptions
server=ThreadingHTTPServer(('0.0.0.0',4000),ServerSentEventsRelay)
from threading import Thread
server=Thread(target=server.serve_forever)
server.start()

try:
    from subprocess import run
    print('startup complete, attempting systemd-notify')
    run(['systemd-notify','--ready'])
except Exception as e:
    print(str(e))
finally:
    print('awaiting requests')
    server.join()