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
        config['ISOLATION']={
            'headers':'client_id,user_id'
        }
        config.write(configFile)

print('config loaded, initializing server')

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
sseClients={} # dict[path]=list[bytesio]
class ServerSentEventsRelay(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,format,*args):
        print(format % args)
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin','*')
        super().end_headers()
        return False
    def do_GET(self):
        if 'headers' in config['ISOLATION']:
            for header in config['ISOLATION'].get('headers').split(','):
                self.path=self.headers[header]+'/'+self.path
        if self.path not in sseClients:
            sseClients[self.path]=[]
        sseClients[self.path].append(self.wfile)
        request.send_response(200)
        request.send_header('Content-Type','text/event-stream')
        request.end_headers()
    def do_POST(self):
        if 'headers' in config['ISOLATION']:
            for header in config['ISOLATION'].get('headers').split(','):
                self.path=self.headers[header]+'/'+self.path
        if(self.path not in sseClients):
            return self.send_error(404)
        for wfile in sseClients[self.path]:
            if wfile.closed:
                sseClients[self.path].remove(wfile)
                continue
            if 'id' in self.headers:
                wfile.write(('id: '+self.headers['id']+'\n').encode())
            if 'event' in self.headers:
                wfile.write(('event: '+self.headers['event']+'\n').encode())
            message=request.rfile.read(int(request.headers['Content-Length'])).decode()
            for part in message.split('\n'):
                wfile.write(('data: '+part+'\n').encode())
            wfile.write('\n'.encode())
            wfile.flush()
        if(len(sseClients[self.path])==0):
            return self.send_error(404)
        self.send_response_only(200)
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Headers', 'event,id')
        self.end_headers()

bind=(config['NETWORK']['IP'],config['NETWORK'].getint('Port'))
server=ThreadingHTTPServer(bind,ServerSentEventsRelay)
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