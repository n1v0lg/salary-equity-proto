from viff.config import load_config, generate_configs, Player
from viff.paillierutil import ViffPaillier
from viff.util import rand
from viff.libs.configobj import ConfigObj
from viff.runtime import Share
import math

def to_share(rt, Zp, val):
    rt.increment_pc()
    el = Zp(val)
    return Share(rt, Zp, el)

def _gen_config_templates(n, t):
    c_templates = generate_configs(n=n, t=t, skip_prss=True)
    return c_templates

def create_global_mpc_details(pid, seckey, peers):
    def pid_from_player(part_id):
        return int(part_id[-1:])  # won't work for IDs greater than 9

    num_players = len(peers)
    threshold = math.floor(num_players / 2)
    threshold = 1 # hard-coded for now
    config_template = _gen_config_templates(num_players, threshold)[pid]
    
    for player, params in config_template.iteritems():
        player_pid = pid_from_player(player)
        params['paillier']['pubkey'] = peers[player_pid]['mpc_details'].pubkey
        params['host'] = peers[player_pid]['address']
        params['port'] = peers[player_pid]['mpc_port']
        if 'seckey' in params['paillier']:
            params['paillier']['seckey'] = seckey

    return config_template    

def create_local_mpc_details(pid, address, port, keysize=1024):
    paillier = ViffPaillier(keysize)
    pk, sec = paillier.generate_keys()
    pl = Player(pid, host=address, port=port,
                pubkey=pk, seckey=None)
    return {'private': sec, 'public': pl}
