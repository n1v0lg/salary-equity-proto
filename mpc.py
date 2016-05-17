from viff.field import GF
from viff.runtime import create_runtime, Runtime
from viff.config import load_config

def run(config):
    Zp = GF(1031)
    id, players = load_config(config)
    input = 7

    def protocol(rt):

        def got_result(result):
            print "Sum:", result
            rt.shutdown()

        x, y, z = rt.shamir_share([1, 2, 3], Zp, input)
        sum = x + y + z
        opened_sum = rt.open(sum)
        opened_sum.addCallback(got_result)

    pre_runtime = create_runtime(id, players, 1)
    pre_runtime.addCallback(protocol)

