from pox.core import core
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.tcp import tcp
from pox.lib.packet.arp import arp
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.util import dpid_to_str
import pox.openflow.libopenflow_01 as of
import hashlib
import logging

log = core.getLogger()
my_log = logging.getLogger("my_logs")

class IPHashLoadBalancer(object):
    def __init__(self, connection):
        self.connection = connection
        self.vip = IPAddr("10.0.0.100")  # Virtual IP
        self.servers = {
            IPAddr("10.0.0.1"): EthAddr("00:00:00:00:00:01"),
            IPAddr("10.0.0.2"): EthAddr("00:00:00:00:00:02"),
            IPAddr("10.0.0.3"): EthAddr("00:00:00:00:00:03"),
            IPAddr("10.0.0.4"): EthAddr("00:00:00:00:00:04")
        }
        self.server_count = len(self.servers)

        # Connect handler to listen for incoming packets
        connection.addListeners(self)

    def hash_ip_port(self, ip, port):
        # Hash function based on IP and port
        hash_value = hashlib.md5(f"{ip}:{port}".encode()).hexdigest()
        return int(hash_value, 16) % self.server_count

    def install_flow(self, match, actions, priority=10, idle_timeout=30, hard_timeout=0):
        # Create a flow mod message
        msg = of.ofp_flow_mod()
        msg.match = match
        msg.priority = priority
        msg.idle_timeout = idle_timeout
        msg.hard_timeout = hard_timeout
        msg.actions = actions
        self.connection.send(msg)
        my_log.info("Flow installed: %s -> %s", match, actions)

    def handle_packet(self, packet, event):
        arp_packet = packet.find(arp)
        if arp_packet:
            if arp_packet.opcode == arp.REQUEST and arp_packet.protodst == self.vip:
                my_log.info("Odpowiedni pakiet arp")
                # Jeśli jeszcze nie mamy MAC dla VIP, zapisujemy pierwszy, który zobaczymy
                if not hasattr(self, 'vip_mac'):
                    self.vip_mac = packet.src
                    my_log.info("Zapisano MAC dla VIP: %s", self.vip_mac)

                arp_reply = arp()
                arp_reply.hwsrc = self.vip_mac
                arp_reply.hwdst = arp_packet.hwsrc
                arp_reply.opcode = arp.REPLY
                arp_reply.protosrc = self.vip
                arp_reply.protodst = arp_packet.protosrc

                eth = ethernet()
                eth.type = ethernet.ARP_TYPE
                eth.src = self.vip_mac
                eth.dst = arp_packet.hwsrc
                eth.payload = arp_reply

                msg = of.ofp_packet_out()
                msg.data = eth.pack()
                msg.actions.append(of.ofp_action_output(port=event.port))
                self.connection.send(msg)

                return
            else:
                my_log.info("Inny pakiet arp")
        
        ip_packet = packet.find(ipv4)
        tcp_packet = packet.find(tcp)

        if not ip_packet or not tcp_packet:
            return
        else:
            my_log.info("ZNALAZŁEM PAKIET!! Typ pakietu {}".format(type(packet)))

        src_ip = ip_packet.srcip
        dst_ip = ip_packet.dstip
        src_port = tcp_packet.srcport

        my_log.info("Pakiet z {} do VIP {} został odebrany. Src port: {}".format(src_ip, dst_ip, src_port))

        # Only handle packets destined to the VIP
        if dst_ip == self.vip:
            server_index = self.hash_ip_port(src_ip, src_port)
            selected_server = self.servers[server_index]

            # Rewrite packet destination to the selected server
            match = of.ofp_match.from_packet(packet, event.port)
            match.nw_dst = self.vip

            actions = [
                of.ofp_action_nw_addr.set_dst(selected_server),
                of.ofp_action_output(port=of.OFPP_NORMAL)
            ]

            # Install flow to forward packets to the selected server
            self.install_flow(match, actions)

            # Send the packet to the selected server
            out = of.ofp_packet_out(data=event.ofp)
            out.actions = actions
            self.connection.send(out)
            my_log.info("Redirected %s:%s -> %s", src_ip, src_port, selected_server)

    def _handle_PacketIn(self, event):
        # log.info("PacketIn odebrany z przełącznika %s", dpid_to_str(event.dpid))
        packet = event.parsed
        if not packet:
            return
        self.handle_packet(packet, event)


class POXLoadBalancer(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        my_log.info("Switch %s has connected", dpid_to_str(event.dpid))
        IPHashLoadBalancer(event.connection)


def launch():
    core.registerNew(POXLoadBalancer)