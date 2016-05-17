from viff.config import load_config, generate_configs, Player
from viff.paillierutil import ViffPaillier
from viff.util import rand
from viff.libs.configobj import ConfigObj

def _gen_config_templates(n, t):
    c_templates = generate_configs(n=n, t=t, skip_prss=True)
    return c_templates

def set_glbl_configs(pid, seckey, servers):
    def pid_from_player(part_id):
        return int(part_id[-1:]) - 1  # won't work for IDs greater than 9

    config_template = _gen_config_templates(3, 1)[pid + 1]
    
    for player, params in config_template.iteritems():
        player_pid = pid_from_player(player)
        params['paillier']['pubkey'] = servers[player_pid]['viff_PK'].pubkey
        params['host'] = servers[player_pid]['address']
        params['port'] = servers[player_pid]['port']
        if 'seckey' in params['paillier']:
            params['paillier']['seckey'] = seckey

    return config_template

def get_lcl_config(params):
    paillier = ViffPaillier(params['keysize'])
    pk, sec = paillier.generate_keys()
    pl = Player(params['temp_id'], host=params['address'], port=int(params['port']),
                pubkey=pk, seckey=None)
    return {'private': sec, 'public': pl}
