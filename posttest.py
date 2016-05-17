import sys
import jsonpickle
import requests
from viff.field import GF
import viff.shamir

if __name__ == '__main__':
    data = [('a', 11), ('b', 7), ('c', 2)]
    mod = 1031
    Zp = GF(mod)
    for owner, value in data:
        el = Zp(value)
        print owner, value, el
        shares = [(8001 + idx, share) for idx, (pl, share) in enumerate(viff.shamir.share(el, 1, 3))]
        for port, share in shares:
            r = requests.post('https://localhost:' + str(port) + '/dataentry', verify='domain.crt', data=jsonpickle.encode((owner, 1, share.value)))
            print r.status_code, r.reason
