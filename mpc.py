from viff.field import GF
from viff.runtime import create_runtime, Runtime
from viff.config import load_config
from viff.runtime import Share

def to_share(rt, Zp, val):
    rt.increment_pc()
    el = Zp(val)
    return Share(rt, Zp, el)

def run(config, data):
    Zp = GF(1031)
    id, players = load_config(config)

    def protocol(rt):
        def got_result(result):
            print "Sum of squares:", result
            rt.shutdown()

        vals = [to_share(rt, Zp, val) for owner, serial, val in data]
        squares = map(lambda x: x * x, vals)
        res = reduce(lambda x, y: x + y, squares)
        opened = rt.open(res)
        opened.addCallback(got_result)

    def errorHandler(failure):
        print "Error: %s" % failure

    pre_runtime = create_runtime(id, players, 1)
    pre_runtime.addCallback(protocol)
    pre_runtime.addErrback(errorHandler)
