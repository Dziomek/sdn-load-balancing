from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.arp import arp
from pox.lib.addresses import IPAddr, EthAddr

import hashlib

log = core.getLogger()

VIP = IPAddr('10.0.0.100')
SERVER_IPS = [IPAddr('10.0.0.1'), IPAddr('10.0.0.2'), IPAddr('10.0.0.3'), IPAddr('10.0.0.4')]

class LoadBalancer(object):
    def __init__(self):
        core.openflow.addListeners(self)
        self.mac_to_port = {}

    def _hash(self, src_ip, dst_ip):
        """ Hash function to determine server based on source and destination IPs."""
        combined = str(src_ip) + str(dst_ip)
        return int(hashlib.md5(combined.encode()).hexdigest(), 16) % len(SERVER_IPS)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        in_port = event.port
        dpid = event.dpid

        # ARP handling
        if packet.type == ethernet.ARP_TYPE:
            self._handle_arp(packet, event, in_port)
            return

        if packet.type != ethernet.IP_TYPE:
            return

        ip_packet = packet.payload

        # Handle packets destined for VIP
        if ip_packet.dstip == VIP:
            if dpid in (5, 6):  # Switch S5
                self._handle_to_vip(event, ip_packet, in_port)
        elif ip_packet.srcip in SERVER_IPS:
            if dpid in (5, 6):  # Switch S5 or S6
                self._handle_from_server(event, ip_packet, in_port)

    def _handle_to_vip(self, event, ip_packet, in_port):
        """ Handle packets destined for the VIP."""
        src_ip = ip_packet.srcip
        dst_ip = ip_packet.dstip

        # Determine which server to forward to
        server_index = self._hash(src_ip, dst_ip)
        selected_server = SERVER_IPS[server_index]

        log.info(f"Switch S5: Forwarding traffic from {src_ip} to {selected_server}")

        # Install flow for this path
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(ip_packet, in_port)

        # Modify the destination IP
        ip_packet.dstip = selected_server
        
        msg.actions.append(of.ofp_action_nw_addr.set_dst(selected_server))
        msg.actions.append(of.ofp_action_output(port=2))  # Example: Forward to port 2

        event.connection.send(msg)

    def _handle_from_server(self, event, ip_packet, in_port):
        """ Handle packets returning from servers to clients."""
        src_ip = ip_packet.srcip

        if src_ip in SERVER_IPS:
            log.info(f"Switch S5/S6: Modifying source IP from {src_ip} to VIP {VIP}")

            # Install flow for this path
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(ip_packet, in_port)

            # Modify the source IP
            ip_packet.srcip = VIP
            
            msg.actions.append(of.ofp_action_nw_addr.set_src(VIP))
            msg.actions.append(of.ofp_action_output(port=1))  # Example: Forward to port 1

            event.connection.send(msg)

    def _handle_arp(self, packet, event, in_port):
        """ Handle ARP packets."""
        arp_packet = packet.payload
        if arp_packet.opcode == arp.REQUEST and arp_packet.protodst == VIP:
            log.info(f"Responding to ARP for VIP {VIP}")

            # Create an ARP reply
            arp_reply = arp()
            arp_reply.hwtype = arp_packet.hwtype
            arp_reply.prototype = arp_packet.prototype
            arp_reply.hwlen = arp_packet.hwlen
            arp_reply.protolen = arp_packet.protolen
            arp_reply.opcode = arp.REPLY
            arp_reply.hwdst = arp_packet.hwsrc
            arp_reply.protosrc = VIP
            arp_reply.protodst = arp_packet.protosrc
            arp_reply.hwsrc = EthAddr("00:00:00:00:00:01")  # Example MAC for VIP

            ethernet_reply = ethernet()
            ethernet_reply.type = ethernet.ARP_TYPE
            ethernet_reply.src = EthAddr("00:00:00:00:00:01")
            ethernet_reply.dst = packet.src
            ethernet_reply.payload = arp_reply

            msg = of.ofp_packet_out()
            msg.data = ethernet_reply.pack()
            msg.actions.append(of.ofp_action_output(port=of.OFPP_IN_PORT))
            msg.in_port = in_port
            event.connection.send(msg)


def launch():
    core.registerNew(LoadBalancer)
