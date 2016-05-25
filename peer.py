from twisted.web import server, resource
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.defer import DeferredList, Deferred
import viff.reactor
from twisted.internet import ssl, reactor
from twisted.internet.task import LoopingCall
from OpenSSL import SSL
import jsonpickle
import copy
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

class Peer:

    def __init__(self, raw_config):
        self.pid = raw_config['self']['pid']
        self.key = raw_config['self']['key']
        self.peers = raw_config['all']
        self.address = self.peers[self.pid]['address']
        self.web_port = self.peers[self.pid]['web_port']
        self.mpc_port = self.peers[self.pid]['mpc_port']
        self.cert = self.peers[self.pid]['cert']
        self.local_mpc_details = viffutil.create_local_mpc_details(self.pid, self.address, self.mpc_port)
        self.global_mpc_details = None
        self.repo = RepoMockup()
        self.session = SessionMockup(set(['a', 'b', 'c']))

    def _generate_data_entry_form(self, template_path, peers):
        with open(template_path) as template:
            parties_js = str(self._get_all_urls(peers, 'data_endpoint')).replace("'", '"')
            print parties_js
            html = template.read() \
                            .replace("NUM_PARTIES_PLACEHOLDER", str(len(peers))) \
                            .replace("THRESHOLD_PLACEHOLDER", str(2)) \
                            .replace("COMP_PARTY_URLS_PLACEHOLDER", parties_js)
            print html
            return html

    def _to_url(self, protocol, address, port, resource_name):
        return '{0}://{1}:{2}/{3}'.format(protocol, address, port, resource_name)

    def _get_all_urls(self, peers, resource_name):
        return [self._to_url('https', peer['address'], peer['web_port'], resource_name) for other_pid, peer in peers.iteritems()]
        
    def _get_peer_urls(self, pid, peers, resource_name):
        return [self._to_url('https', peer['address'], peer['web_port'], resource_name) for other_pid, peer in peers.iteritems() if pid != other_pid]
        
    def _response_received(self, response_wrapper):
        response = response_wrapper.result
        finished = Deferred()
        response.deliverBody(twistedutil.ConfigReader(finished))
        return finished

    def process_other_peer_details(self, peer_details, pid, peers, local_details):
        for flag, peer in peer_details:
            decoded = jsonpickle.decode(peer)
            peers[decoded.id]['mpc_details'] = decoded
        peers[pid]['mpc_details'] = local_details['public']
        self.global_mpc_details  = viffutil.create_global_mpc_details(pid, local_details['private'], peers)
        return self.global_mpc_details

    def start_web_server(self, pid, peers, address, port, key, cert, for_other_peers):
        root = resource.Resource()
        root.putChild('mpc_details', twistedutil.MPCDetails(for_other_peers))
        html = self._generate_data_entry_form('submit.html', peers)
        root.putChild('data_entry_form', twistedutil.DataEntryForm(html))
        peer_urls = self._get_peer_urls(pid, peers, 'mpc_details')
        root.putChild('data_endpoint', twistedutil.DataEndpoint(self.repo, self.session, peer_urls))
        site = server.Site(root)
        context_factory = ssl.DefaultOpenSSLContextFactory(key, cert)
        reactor.listenSSL(port, site, context_factory)

    def setup_mpc(self, pid, local_mpc_details, peers):
        
        class ConfigWaiter:
            def success(self, response):
                self.loop.result = response
                self.loop.stop()
                return

            def failure(self, err):
                return

            def check_server(self, url):
                contextFactory = twistedutil.WebClientContextFactory()
                agent = Agent(reactor, contextFactory)
                d = agent.request('GET', url)
                d.addCallback(self.success)
                d.addErrback(self.failure)
                return d

        urls = self._get_peer_urls(pid, peers, 'mpc_details')
        deferreds = []
        for url in urls:
            lw = ConfigWaiter()
            l = LoopingCall(lw.check_server, url)
            lw.loop = l
            d = l.start(1.0)
            d.addCallback(self._response_received)
            deferreds.append(d)
        dl = DeferredList(deferreds)
        dl.addCallback(self.process_other_peer_details, pid, peers, local_mpc_details)
        return dl

    def wait_for_data(self, config, session, repo):

        def data_ready(_, config):
            return config

        class DataWaiter:
            def check_data(self, input_parties):
                print 'Waiting on input parties:', list(input_parties)
                if not input_parties:
                    self.loop.stop()
                return config

        lw = DataWaiter()
        l = LoopingCall(lw.check_data, session.input_parties)
        lw.loop = l
        d = l.start(1.0)
        d.addCallback(data_ready, config)
        return d    

    def run_mpc_protocol(self, config, repo):
        import sumofsquares
        sumofsquares.run(config, repo)

    def run(self):
        self.start_web_server(self.pid, self.peers, self.address, self.web_port, self.key, self.cert, self.local_mpc_details['public'])
        self.setup_mpc(self.pid, self.local_mpc_details, self.peers) \
            .addCallback(self.wait_for_data, self.session, self.repo) \
            .addCallback(self.run_mpc_protocol, self.repo)
        reactor.run()

if __name__ == '__main__':
    from config import _config
    peer = Peer(_config)
    peer.run()
