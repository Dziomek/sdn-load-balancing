# -*- coding: utf-8 -*-
from pox.core import core
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.tcp import tcp
from pox.lib.packet.udp import udp
from pox.lib.addresses import IPAddr, EthAddr
import pox.openflow.libopenflow_01 as of
import random
import hashlib

log = core.getLogger()

# Lista serwerów
SERVERS = [
    {"ip": IPAddr("10.0.0.1")},
    {"ip": IPAddr("10.0.0.2")},
    {"ip": IPAddr("10.0.0.3")},
    {"ip": IPAddr("10.0.0.4")}
]

class IPHashLoadBalancer(object):
    def __init__(self, connection):
        self.connection = connection
        self.connection.addListeners(self)
        self.mac_to_port = {}

    def select_server(self, src_ip):
        # Funkcja IP Hash
        hash_value = int(hashlib.md5(str(src_ip).encode()).hexdigest(), 16)
        server_index = hash_value % len(SERVERS)
        return SERVERS[server_index]

    def _handle_PacketIn(self, event):
        packet = event.parsed

        if not packet.parsed:
            log.warning("Nieparsowalny pakiet")
            return

        # Obsługa ruchu tylko IP (IPv4)
        if not isinstance(packet.next, ipv4):
            return

        ip_packet = packet.next

        # Obsługa tylko TCP i UDP
        if not isinstance(ip_packet.next, (tcp, udp)):
            return

        src_ip = ip_packet.srcip
        dst_ip = ip_packet.dstip

        # Jeżeli ruch jest skierowany do serwera
        if dst_ip in [server["ip"] for server in SERVERS]:
            log.info(f"Pakiet skierowany do serwera: {dst_ip}")
            return

        # Wybierz serwer na podstawie IP Hash
        selected_server = self.select_server(src_ip)

        log.info(f"Przekierowanie ruchu od {src_ip} do serwera {selected_server['ip']}")

        # Utwórz flow dla ruchu klient → serwer
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.idle_timeout = 10
        msg.hard_timeout = 30
        msg.actions.append(of.ofp_action_nw_addr.set_dst(selected_server["ip"]))
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        self.connection.send(msg)

        # Utwórz flow dla ruchu serwer → klient
        msg_back = of.ofp_flow_mod()
        msg_back.match.dl_dst = packet.src
        msg_back.match.nw_src = selected_server["ip"]
        msg_back.actions.append(of.ofp_action_dl_addr.set_src(packet.dst))
        msg_back.actions.append(of.ofp_action_nw_addr.set_src(ip_packet.dstip))
        msg_back.actions.append(of.ofp_action_output(port=event.port))
        self.connection.send(msg_back)

        # Wyślij pakiet natychmiast
        out = of.ofp_packet_out()
        out.data = event.ofp
        out.actions.append(of.ofp_action_nw_addr.set_dst(selected_server["ip"]))
        out.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        self.connection.send(out)

class IPHashController(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.info("Połączenie z przełącznikiem %s" % event.connection)
        IPHashLoadBalancer(event.connection)

def launch():
    core.registerNew(IPHashController)