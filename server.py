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
from twisted.internet import ssl, reactor
from twisted.internet.task import LoopingCall
from OpenSSL import SSL
import errno    
import jsonpickle
from urllib2 import urlopen, URLError
import requests
import httplib2
import viffutil
import sys
import copy
import time
import mpc
from twisted.internet.protocol import ReconnectingClientFactory

# TODO: prevent twisted from dumping stacktrace to client

pid = -1
servers = [{'address': 'localhost','web_port': 8001, 'port': 9001, 'temp_id': 1, 'viff_PK': None, 'keysize': 1024, 'cert': 'ca.cert'}, 
           {'address': 'localhost','web_port': 8002, 'port': 9002, 'temp_id': 2, 'viff_PK': None, 'keysize': 1024, 'cert': 'ca.cert'},
           {'address': 'localhost','web_port': 8003, 'port': 9003, 'temp_id': 3, 'viff_PK': None, 'keysize': 1024, 'cert': 'ca.cert'}] 
participants = set(['a', 'b', 'c'])
received_data = []
seckey = None

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

class EntryFormResource(resource.Resource):
    isLeaf = True

    def __init__(self, html):
        resource.Resource.__init__(self)
        self.html = html

    def render_GET(self, request):
        # figure out the twisted way to do this
        return self.html

class DataEntryResource(resource.Resource):
    isLeaf = True

    def __init__(self, datastore, waiting_on):
        resource.Resource.__init__(self)
        self.valid_origins = ['https://localhost:8001', 'https://localhost:8002', 'https://localhost:8003']
        self.datastore = datastore
        self.waiting_on = waiting_on

    def render_POST(self, request):
        origin = request.getHeader('origin')
        if origin in self.valid_origins:
            request.setHeader('Access-Control-Allow-Origin', origin)
            request.setHeader('Access-Control-Allow-Methods', 'POST')
        
        raw = request.content.getvalue()
        data = jsonpickle.decode(raw) # outrageously insecure
        self.datastore.append(data)
        self.waiting_on.discard(data[0])
        request.write('{response: "OK"}') 
        request.finish()
    
        return NOT_DONE_YET

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
        # print 'Finished receiving body:', reason.getErrorMessage()
        self.finished.callback(self.data)

def process_configs(configs, config):
    for flag, raw_config in configs:
        decoded = jsonpickle.decode(raw_config)
        servers[decoded.id - 1]['viff_PK'] = decoded
    servers[pid]['viff_PK'] = config['public']
    complete = viffutil.set_glbl_configs(pid, config['private'], servers)
    return complete

class DataWaiter:
    def check_data(self, participants):
        print 'Waiting on participants:', list(participants)
        if not participants:
            self.loop.stop()
        return config

def data_ready(_, config):
    return config

def wait_for_data(config, participants):
    lw = DataWaiter()
    l = LoopingCall(lw.check_data, participants)
    lw.loop = l
    d = l.start(1.0)
    d.addCallback(data_ready, config)
    return d

def response_received(response_wrapper):
    response = response_wrapper.result
    finished = Deferred()
    response.deliverBody(BeginningPrinter(finished))
    return finished

# def check_server(url):
#     contextFactory = WebClientContextFactory()
#     agent = Agent(reactor, contextFactory)
#     return agent.request('GET', url)
        
# class LoopingCallWrap:
#     def __init__(self, f, *args):
#         self.args = (f, ) + args
#         self.loop = LoopingCall(self.wrapper, *self.args)
        
#     def wrapper(self, f, args):
#         d = f(args)
#         d.addCallback(self.success)
#         d.addErrback(self.failure)
#         return d

#     def success(self, result):
#         self.loop.result = result
#         self.loop.stop()
#         return

#     def failure(self, err):
#         return

#     def start(self, duration):
#         d = self.loop.start(duration)
#         return d

class ConfigWaiter:
    def success(self, response):
        self.loop.result = response
        self.loop.stop()
        return

    def failure(self, err):
        return

    def check_server(self, url):
        contextFactory = WebClientContextFactory()
        agent = Agent(reactor, contextFactory)
        d = agent.request('GET', url)
        d.addCallback(self.success)
        d.addErrback(self.failure)
        return d

def start_client(config):
    urls = ['{0}://{1}:{2}/config'.format('https', server['address'], server['web_port']) for sid, server in enumerate(servers) if pid != sid]
    deferreds = []
    for url in urls:
        lw = ConfigWaiter()
        l = LoopingCall(lw.check_server, url)
        lw.loop = l
        d = l.start(1.0)
        d.addCallback(response_received)
        deferreds.append(d)
    dl = DeferredList(deferreds)
    dl.addCallback(process_configs, config)
    return dl

def start_server(config):
    root = resource.Resource()
    html = open('submit.html').read()
    root.putChild('config', ConfigResource(config))
    root.putChild('dataentry', DataEntryResource(received_data, participants))
    root.putChild('entryform', EntryFormResource(html))
    site = server.Site(root)

    myContextFactory = ssl.DefaultOpenSSLContextFactory(
        'player-{0}.key'.format(pid + 1), 'player-{0}.cert'.format(pid + 1)
        )
    reactor.listenSSL(servers[pid]['web_port'], site, myContextFactory)
        
if __name__ == '__main__':
    pid = int(sys.argv[1])
    config = configure_mpc_client(pid, servers)
    start_server(config)
    d = start_client(config)
    d.addCallback(wait_for_data, participants)
    d.addCallback(mpc.run, received_data)
    reactor.run()
