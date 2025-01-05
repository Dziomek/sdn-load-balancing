from pox.core import core
from pox.lib.packet import ethernet
from pox.lib.addresses import IPAddr
from pox.openflow.libopenflow_01 import of, ofp_flow_mod, ofp_match, ofp_action_output
import random

log = core.getLogger()

class LoadBalancer:
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        # Dla każdego nowego połączenia
        log.info("Switch %s connected", event.dpid)

        # Zdefiniowanie serwerów
        servers = {
            'h1': 1,  # Port 1 switcha s1
            'h2': 2,  # Port 2 switcha s1
            'h3': 3,  # Port 3 switcha s3
            'h4': 4   # Port 4 switcha s3
        }

        # Inicjalizacja STP
        event.connection.send(ofp_flow_mod(command=of.OFPFC_ADD, priority=10, match=ofp_match(), actions=[ofp_action_output(port=of.OFPP_CONTROLLER)]))
        
        # Reguły load balancing na podstawie źródłowego IP
        for src_ip in range(1, 5):  # Załóżmy, że src IP to 192.168.1.x
            ip_src = IPAddr(f"10.0.0.{src_ip}")
            
            # Hashowanie IP do portu (tutaj możemy po prostu użyć prostego algorytmu)
            hash_value = hash(ip_src) % len(servers)
            chosen_server = list(servers.keys())[hash_value]
            port = servers[chosen_server]

            match = ofp_match()
            match.dl_type = ethernet.ETH_TYPE_IP
            match.nw_src = ip_src

            # Reguła przekierowania
            actions = [ofp_action_output(port=port)]
            event.connection.send(ofp_flow_mod(command=of.OFPFC_ADD, match=match, actions=actions, priority=100))
            log.info(f"Load balancing rule: IP {ip_src} -> {chosen_server} (Port {port})")

# Inicjalizacja
def launch():
    core.registerNew(LoadBalancer)
