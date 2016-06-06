from twisted.web import server, resource
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.defer import DeferredList, Deferred
import viff.reactor
from twisted.internet import ssl, reactor
from twisted.internet.task import LoopingCall
from OpenSSL import SSL
import jsonpickle
import viffutil
import twistedutil
        
class RepoMockup:

    def __init__(self):
        self._store = {'shares': []}

    def add_share(self, share):
        self._store['shares'].append(share)

    def get_shares(self):
        return self._store['shares']

class SessionMockup:

    def __init__(self, input_parties):
        self.input_parties = input_parties

def _to_url(protocol, address, port, resource_name):
        return '{0}://{1}:{2}/{3}'.format(protocol, address, port, resource_name)

def _get_all_urls(peers, resource_name):
    return [_to_url('https', peer['address'], peer['web_port'], resource_name) for other_pid, peer in peers.iteritems()]
        
def _get_peer_urls(pid, peers, resource_name):
    return [_to_url('https', peer['address'], peer['web_port'], resource_name) for other_pid, peer in peers.iteritems() if pid != other_pid]

class LocalConfig:
    def __init__(self, pid, key, cert, peers, address, web_port, mpc_port):
        self.pid = pid
        self.key = key
        self.cert = cert
        self.peers = peers
        self.address = address
        self.web_port = web_port
        self.mpc_port = mpc_port
        self.local_mpc_details = viffutil.create_local_mpc_details(self.pid, self.address, self.mpc_port)
        
def _generate_data_entry_form(peers, template_path):
    with open(template_path) as template:
        parties_js = str(_get_all_urls(peers, 'data_entry')).replace("'", '"')
        html = template.read() \
                    .replace("NUM_PARTIES_PLACEHOLDER", str(len(peers))) \
                    .replace("THRESHOLD_PLACEHOLDER", str(2)) \
                    .replace("COMP_PARTY_URLS_PLACEHOLDER", parties_js)
        return html
    
def start_web_server(pid, peers, key, cert, port, public_mpc_details, repo, session):
    root = resource.Resource()
    root.putChild('mpc_details', twistedutil.MPCDetails(public_mpc_details))
    html = _generate_data_entry_form(peers, 'submit.html')
    peer_urls = _get_peer_urls(pid, peers, 'mpc_details')
    root.putChild('data_entry', twistedutil.DataEntry(html, repo, session, peer_urls))
    site = server.Site(root)
    context_factory = ssl.DefaultOpenSSLContextFactory(key, cert)
    reactor.listenSSL(port, site, context_factory)

def setup_phase(pid, peers, local_mpc_details):
        
    def _response_received(response_wrapper):
        response = response_wrapper.result
        finished = Deferred()
        response.deliverBody(twistedutil.ConfigReader(finished))
        return finished
    
    def _configure_mpc(peer_details, pid, peers, local_details):
        for flag, peer in peer_details:
            decoded = jsonpickle.decode(peer)
            peers[decoded.id]['mpc_details'] = decoded
        peers[pid]['mpc_details'] = local_details['public']
        ready_mpc_config  = viffutil.create_global_mpc_details(pid, local_details['private'], peers)
        # ready_mpc_config.write()
        return ready_mpc_config
    
    class ConfigWaiter:
    
        def success(self, response):
            self.loop.result = response
            self.loop.stop()
            return
    
        def failure(self, err):
            return
    
        def check_server(self, url):
            # TODO: take agent initialization outside this method
            contextFactory = twistedutil.WebClientContextFactory()
            agent = Agent(reactor, contextFactory)
            d = agent.request('GET', url)
            d.addCallback(self.success)
            d.addErrback(self.failure)
            return d
    
    urls = _get_peer_urls(pid, peers, 'mpc_details')
    deferreds = []
    for url in urls:
        lw = ConfigWaiter()
        l = LoopingCall(lw.check_server, url)
        lw.loop = l
        d = l.start(1.0)
        d.addCallback(_response_received)
        deferreds.append(d)
    dl = DeferredList(deferreds)
    dl.addCallback(_configure_mpc, pid, peers, local_mpc_details)
    dl.addCallback(viffutil.create_preruntime)
    return dl

def input_phase(rt, session, repo):

    def data_ready(_, rt):
        return rt

    class DataWaiter:
        def check_data(self, input_parties):
            print 'Waiting on input parties:', list(input_parties)
            if not input_parties:
                self.loop.stop()
            return rt

    lw = DataWaiter()
    l = LoopingCall(lw.check_data, session.input_parties)
    lw.loop = l
    d = l.start(1.0)
    d.addCallback(data_ready, rt)
    return d

def parse_config(config):
    pid = config['self']['pid']
    kwargs = dict(config['self'], **config['all'][pid])
    kwargs['peers'] = config['all']
    return LocalConfig(**kwargs)
    
def prepare_runtime_and_input(config, repo, session):
    lc = parse_config(config)
    start_web_server(lc.pid, lc.peers, lc.key, lc.cert, lc.web_port, 
                     lc.local_mpc_details['public'], repo, session)
    return setup_phase(lc.pid, lc.peers, lc.local_mpc_details) \
                .addCallback(input_phase, session, repo)
            
def run_protocol(rt, p):
    rt.addCallback(p)
    reactor.run()
