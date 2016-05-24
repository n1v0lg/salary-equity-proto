from optparse import OptionParser
from viff.field import GF
from viff.runtime import create_runtime, Runtime
from viff.config import load_config
import viffutil

def run(config, repo):
    Zp = GF(1031)
    id, players = load_config(config)

    def protocol(rt):
        def got_result(result):
            print "Sum of squares:", result
            rt.shutdown()

        vals = [viffutil.to_share(rt, Zp, val) for owner, serial, val in repo.get_shares()]
        squares = map(lambda x: x * x, vals)
        res = reduce(lambda x, y: x + y, squares)
        opened = rt.open(res)
        opened.addCallback(got_result)

    def errorHandler(failure):
        print "Error: %s" % failure

    parser = OptionParser()
    Runtime.add_options(parser)
    options, args = parser.parse_args()
    options.ssl = True
    
    pre_runtime = create_runtime(id, players, 1, options)
    pre_runtime.addCallback(protocol)
    pre_runtime.addErrback(errorHandler)
