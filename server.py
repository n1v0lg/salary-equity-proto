from twisted.internet.protocol import Factory, Protocol
from twisted.web import server, resource
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.ssl import ClientContextFactory
from twisted.python.log import err
from twisted.internet.task import deferLater
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredList, Deferred
from twisted.web.server import NOT_DONE_YET
import viff.reactor
# viff.reactor.install()
from twisted.internet import ssl, reactor
from twisted.internet.task import LoopingCall

from multiprocessing import Process
import jsonpickle
from urllib2 import urlopen
import httplib2
import viffutil
import sys
import time
import mpc

pid = -1
servers = [{'address': 'localhost','web_port': 8001, 'port': 9001, 'temp_id': 1, 'viff_PK': None, 'keysize': 1024, 'crt': 'domain.crt'}, 
           {'address': 'localhost','web_port': 8002, 'port': 9002, 'temp_id': 2, 'viff_PK': None, 'keysize': 1024, 'crt': 'domain.crt'},
           {'address': 'localhost','web_port': 8003, 'port': 9003, 'temp_id': 3, 'viff_PK': None, 'keysize': 1024, 'crt': 'domain.crt'}] 
seckey = None

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

class ConfigResource(resource.Resource):
    isLeaf = True

    def __init__(self, config):
        resource.Resource.__init__(self)
        self.config = jsonpickle.encode(config['public'])

    def render_GET(self, request):
        return self.config

def configure_mpc_client(pid, parameters):
    template = viffutil._gen_config_templates(3, 1)
    local_config = viffutil.get_lcl_config(parameters[pid])
    return local_config

# could use twisted callbacks for this
# def get_other_configs(config):
#     for sid, server in enumerate(servers):
#         if pid != sid:
#             h = httplib2.Http(ca_certs=server['crt'])
#             url = '{0}://{1}:{2}/config'.format('https', server['address'], server['web_port'])
#             received = False
#             other_config = None
#             while not received:
#                 try:
#                     resp, content = h.request(url, 'GET')
#                     other_config = jsonpickle.decode(content)
#                 except Exception:
#                     time.sleep(1)
#                 else:
#                     received = True
#             server['viff_PK'] = other_config
#         else:
#             server['viff_PK'] = config['public']
#     config = viffutil.set_glbl_configs(pid, config['private'], servers)
#     return config

def deferredSleep(duration):
    return deferLater(reactor, duration, lambda: None)

@inlineCallbacks
def wait_for_server(url):
    while True:
        try:
            # TODO: use twisted here too
            urlopen(url)
        except Exception as e:
            yield deferredSleep(1.0)
        else:
            returnValue(url)

class BeginningPrinter(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.data = ''
        self.remaining = 1024 * 10

    def dataReceived(self, bytes):
        if self.remaining:
            display = bytes[:self.remaining]
            self.data += str(display)
            self.remaining -= len(display)

    def connectionLost(self, reason):
        print 'Finished receiving body:', reason.getErrorMessage()
        self.finished.callback(self.data)

def process_responses(responses):
    defs = []
    for flag, resp in responses:
        finished = Deferred()
        resp.deliverBody(BeginningPrinter(finished))
        defs.append(finished)
    # print defs
    return DeferredList(defs)

def process_configs(configs, config):
    for flag, raw_config in configs:
        decoded = jsonpickle.decode(raw_config)
        servers[decoded.id - 1]['viff_PK'] = decoded
    servers[pid]['viff_PK'] = config['public']
    complete = viffutil.set_glbl_configs(pid, config['private'], servers)
    return complete

def servers_ready(urls):
    contextFactory = WebClientContextFactory()
    agent = Agent(reactor, contextFactory)
    dl = DeferredList([agent.request('GET', url) for flag, url in urls])
    return dl
    
def start_client(config):
    urls = ['{0}://{1}:{2}/config'.format('https', server['address'], server['web_port']) for sid, server in enumerate(servers) if pid != sid]
    dl = DeferredList([wait_for_server(url) for url in urls])
    dl.addCallback(servers_ready)
    dl.addCallback(process_responses)
    dl.addCallback(process_configs, config)
    return dl

def start_server(config):
    root = resource.Resource()
    root.putChild('config', ConfigResource(config))
    site = server.Site(root)
    # domain.key is a contended resource as of now
    reactor.listenSSL(servers[pid]['web_port'], site, ssl.DefaultOpenSSLContextFactory('domain.key', 'domain.crt'))
        
if __name__ == '__main__':
    pid = int(sys.argv[1])
    config = configure_mpc_client(pid, servers)
    start_server(config)
    d = start_client(config)
    d.addCallback(mpc.run)
    reactor.run()
