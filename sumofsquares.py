from viff.field import GF
import viff.reactor
from twisted.internet import reactor
import viffutil
import peer
from config import _config

def protocol(rt):
    def got_result(result):
        print "Sum of squares:", result
        rt.shutdown()

    Zp = GF(1031)
    vals = [viffutil.to_share(rt, Zp, val) for owner, serial, val in repo.get_shares()]
    squares = map(lambda x: x * x, vals)
    res = reduce(lambda x, y: x + y, squares)
    opened = rt.open(res)
    opened.addCallback(got_result)

def errorHandler(failure):
    print "Error: %s" % failure

repo = peer.RepoMockup()
session = peer.SessionMockup(set(['a', 'b', 'c']))

cluster = peer.start_cluster(_config, repo, session)
cluster.addCallback(protocol)
reactor.run()
