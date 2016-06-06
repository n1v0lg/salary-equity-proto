from twisted.internet.ssl import ClientContextFactory
from twisted.internet.protocol import Factory, Protocol
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
import jsonpickle

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

class ConfigReader(Protocol):
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
        self.finished.callback(self.data)

class DataEntry(resource.Resource):
    isLeaf = True

    def __init__(self, html, repo, session, peer_origins):
        resource.Resource.__init__(self)
        self.html = html
        self.peer_origins = peer_origins
        self.repo = repo
        self.session = session

    def render_GET(self, request):
        # figure out the twisted way to do this
        return self.html

    def render_POST(self, request):
        # origin = request.getHeader('origin')
        # if origin in self.peer_origins:
        #     request.setHeader('Access-Control-Allow-Origin', origin)
        #     request.setHeader('Access-Control-Allow-Methods', 'POST')
        raw = request.content.getvalue()
        data = jsonpickle.decode(raw) # outrageously insecure
        print data
        self.repo.add_share(data)
        self.session.input_parties.discard(data[0])
        # request.write('{}') 
        # request.finish()
        return "<html>OK</html>"
        # return NOT_DONE_YET

class MPCDetails(resource.Resource):
    isLeaf = True

    def __init__(self, mpc_details):
        resource.Resource.__init__(self)
        self.mpc_details = jsonpickle.encode(mpc_details)

    def render_GET(self, request):
        return self.mpc_details
