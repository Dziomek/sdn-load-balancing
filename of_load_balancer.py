from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.ethernet import ethernet
from pox.lib.addresses import IPAddr, EthAddr
import hashlib

log = core.getLogger()

STATIC_PATHS = {
    ('h5', 'h1'): ['s5', 's2', 's1'],
    ('h5', 'h2'): ['s5', 's2', 's1'],
    ('h5', 'h3'): ['s5', 's2', 's3'],
    ('h5', 'h4'): ['s5', 's2', 's3'],

    ('h6', 'h1'): ['s5', 's2', 's1'],
    ('h6', 'h2'): ['s5', 's2', 's1'],
    ('h6', 'h3'): ['s5', 's2', 's3'],
    ('h6', 'h4'): ['s5', 's2', 's3'],

    ('h7', 'h1'): ['s6', 's4', 's1'],
    ('h7', 'h2'): ['s6', 's4', 's1'],
    ('h7', 'h3'): ['s6', 's4', 's3'],
    ('h7', 'h4'): ['s6', 's4', 's3'],

    ('h8', 'h1'): ['s6', 's4', 's1'],
    ('h8', 'h2'): ['s6', 's4', 's1'],
    ('h8', 'h3'): ['s6', 's4', 's3'],
    ('h8', 'h4'): ['s6', 's4', 's3'],
}
SERVERS = ['h1', 'h2', 'h3', 'h4']
VIP = "10.0.0.100"
VIP_MAC = EthAddr("00:00:00:00:10:00")  # Fałszywy MAC VIP

class OpenFlowLoadBalancer:
    def __init__(self, connection):
        self.connection = connection
        self.connection.addListeners(self)

        # Instalujemy statyczne flowy na przełącznikach brzegowych
        self.install_static_flows(connection.dpid)

    def install_static_flows(self, dpid):
        """Instaluje statyczne flowy na przełącznikach brzegowych."""
        switch_name = f"s{dpid}"
        EDGE_SWITCHES = { #switch, port
            "s1": 1,  
            "s3": 1,
            "s5": 1,
            "s6": 1
        }
        if switch_name in EDGE_SWITCHES:
            vip_port = EDGE_SWITCHES[switch_name]

            # Flow dla ARP
            msg_arp = of.ofp_flow_mod()
            msg_arp.match = of.ofp_match(dl_type=0x0806, nw_dst=VIP)
            msg_arp.actions.append(of.ofp_action_output(port=vip_port))
            self.connection.send(msg_arp)

            # Flow dla ruchu IP do VIP
            msg_ip = of.ofp_flow_mod()
            msg_ip.match = of.ofp_match(dl_type=0x0800, nw_dst=VIP)
            msg_ip.actions.append(of.ofp_action_output(port=vip_port))
            self.connection.send(msg_ip)

            log.info("Zainstalowano statyczne flowy na %s do VIP %s", switch_name, VIP)

    def hash_ip_port(self, src_ip, src_port):
        """Hashuje IP i port źródłowy, wybiera serwer."""
        hash_value = hashlib.md5(f"{src_ip}:{src_port}".encode()).hexdigest()
        return int(hash_value, 16) % len(SERVERS)

    def install_flow(self, dpid, match, actions):
        """Instaluje flow na przełączniku."""
        msg = of.ofp_flow_mod()
        msg.match = match
        msg.actions = actions
        core.openflow.sendToDPID(dpid, msg)
        log.info("Instaluję flow na %s: match=%s, actions=%s", dpid, match, actions)

    def _handle_PacketIn(self, event):
        """Obsługa pakietów przychodzących do kontrolera."""
        packet = event.parsed
        ip_packet = packet.find(ipv4)

        if not ip_packet:
            return
        
        src_ip = str(ip_packet.srcip)
        dst_ip = str(ip_packet.dstip)
        src_port = event.port

        log.info("ZNALAZŁEM PAKIET!! SRC_IP: %s DST_IP: %s SRC_PORT %s", src_ip, dst_ip, src_port)

        if dst_ip == "10.0.0.100":  # Ruch do VIP
            server_index = self.hash_ip_port(src_ip, src_port)
            selected_server = SERVERS[server_index]

            # Pobranie ścieżki
            path = STATIC_PATHS.get((f"h{src_ip[-1]}", selected_server))
            if not path:
                log.error("Brak ścieżki dla %s -> %s", src_ip, selected_server)
                return

            log.info("Wybrana ścieżka dla %s -> %s: %s", src_ip, selected_server, path)

            # Instalacja flowów na przełącznikach ścieżki (od końca do początku)
            for switch in reversed(path):
                match = of.ofp_match(dl_type=0x0800, nw_src=src_ip, nw_dst=dst_ip)
                actions = [of.ofp_action_output(port=event.port)]
                self.install_flow(switch, match, actions)

class POXController:
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.info("Przełącznik podłączony: %s", event.dpid)
        OpenFlowLoadBalancer(event.connection)

def launch():
    core.registerNew(POXController)