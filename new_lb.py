from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.arp import arp
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet import tcp, udp

import hashlib

log = core.getLogger()

VMAC = EthAddr("00:00:00:00:00:09")
VIP = IPAddr('10.0.0.9')

H5 = IPAddr('10.0.0.5')
H6 = IPAddr('10.0.0.6')
H7 = IPAddr('10.0.0.7')
H8 = IPAddr('10.0.0.8')

S1 = IPAddr('10.0.0.1')
S2 = IPAddr('10.0.0.2')
S3 = IPAddr('10.0.0.3')
S4 = IPAddr('10.0.0.4')
SERVER_IPS = [S1, S2, S3, S4]

S1MAC = EthAddr("00:00:00:00:00:01")
S2MAC = EthAddr("00:00:00:00:00:02")
S3MAC = EthAddr("00:00:00:00:00:03")
S4MAC = EthAddr("00:00:00:00:00:04")
SERVER_MACS = [S1MAC, S2MAC, S3MAC, S4MAC]

class LoadBalancer(object):
    def __init__(self):
        core.openflow.addListeners(self)
        self.mac_to_port = {}

    def _hash(self, src_ip, dst_ip):
        """ Hash function to determine server based on source and destination IPs."""
        combined = str(src_ip) + str(dst_ip)
        return int(hashlib.md5(combined.encode()).hexdigest(), 16) % len(SERVER_IPS)

    def install_flow(self, event, ip_packet, in_port, selected_server, selected_mac, out_port, dpid):
        # Install flow for this path
        msg = of.ofp_flow_mod()
        match = of.ofp_match()

        match.in_port = in_port 
        match.dl_src = event.parsed.src  # Source MAC address
        match.dl_dst = event.parsed.dst  # Destination MAC address
        match.nw_src = ip_packet.srcip  # Source IP address
        match.nw_dst = ip_packet.dstip  # Destination IP address
        
        transport_packet = ip_packet.payload
        match.tp_src = transport_packet.srcport  # Source port
        match.tp_dst = transport_packet.dstport  # Destination port
    
        msg.match = match
        
        msg.actions.append(of.ofp_action_nw_addr.set_dst(selected_server))
        msg.actions.append(of.ofp_action_dl_addr.set_dst(selected_mac))
        msg.actions.append(of.ofp_action_output(port=out_port))

        connection = None
        for conn in core.openflow.connections.values():
            if conn.dpid == dpid:
                connection = conn
                break

        if connection:
            connection.send(msg)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        in_port = event.port
        dpid = event.dpid

        # ARP handling
        #if packet.type == ethernet.ARP_TYPE:
        #    self._handle_arp(packet, event, in_port)
        #    return

        #if packet.type != ethernet.IP_TYPE:
        #    return

        ip_packet = packet.find("ipv4")
        if ip_packet is None:
            return  # Jeśli pakiet nie jest IPv4, kończymy

        transport_packet = ip_packet.payload
        if isinstance(transport_packet, tcp) or isinstance(transport_packet, udp):
            # Sprawdzamy, czy porty odpowiadają domyślnym portom iperf (np. port 5001)
            if transport_packet.dstport == 5001 or transport_packet.srcport == 5001:
                # Pakiet jest związany z iperf, przechodzi dalej
                pass
            else:
                return  # Jeśli port nie odpowiada, ignorujemy pakiet
        else:
            return  # Jeśli nie ma danych transportowych (TCP/UDP), ignorujemy pakiet

        ip_packet = packet.payload

        # Handle packets destined for VIP
        if ip_packet.dstip == VIP and event.parsed.dst == VMAC:
            if dpid in (5, 6):  # Switch S5 or S6
                self._handle_to_vip(event, ip_packet, in_port)
                
        elif ip_packet.srcip in SERVER_IPS:
            if dpid in (5, 6):  # Switch S5 or S6
                self._handle_from_server(event, ip_packet, in_port, dpid)

    def _handle_to_vip(self, event, ip_packet, in_port):
        """ Handle packets destined for the VIP."""
        src_ip = ip_packet.srcip
        dst_ip = ip_packet.dstip

        # Determine which server to forward to
        server_index = self._hash(src_ip, dst_ip)
        selected_server = SERVER_IPS[server_index]
        selected_mac = SERVER_MACS[server_index]

        log.info(f"Switch S{event.dpid}: Forwarding traffic from {src_ip} to {selected_server}")

        if src_ip in (H5, H6):
            if selected_server == S1:
                self.install_flow(event, ip_packet, in_port, selected_server, selected_mac, 3, 5)

                ip_packet.dstip = selected_server
                event.parsed.dst = selected_mac
                
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 1, 2)
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 1, 1)
                
            elif selected_server == S2:
                self.install_flow(event, ip_packet, in_port, selected_server, selected_mac, 3, 5)

                ip_packet.dstip = selected_server
                event.parsed.dst = selected_mac
                
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 1, 2)
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 2, 1)

            elif selected_server == S3:
                self.install_flow(event, ip_packet, in_port, selected_server, selected_mac, 3, 5)

                ip_packet.dstip = selected_server
                event.parsed.dst = selected_mac
                
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 4, 2)
                self.install_flow(event, ip_packet, 5, selected_server, selected_mac, 1, 3)

            elif selected_server == S4:
                self.install_flow(event, ip_packet, in_port, selected_server, selected_mac, 3, 5)

                ip_packet.dstip = selected_server
                event.parsed.dst = selected_mac
                
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 4, 2)
                self.install_flow(event, ip_packet, 5, selected_server, selected_mac, 2, 3)

        elif src_ip in (H7, H8):
            if selected_server == S1:
                self.install_flow(event, ip_packet, in_port, selected_server, selected_mac, 3, 6)

                ip_packet.dstip = selected_server
                event.parsed.dst = selected_mac
                
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 4, 4)
                self.install_flow(event, ip_packet, 5, selected_server, selected_mac, 1, 1)

            elif selected_server == S2:
                self.install_flow(event, ip_packet, in_port, selected_server, selected_mac, 3, 6)

                ip_packet.dstip = selected_server
                event.parsed.dst = selected_mac
                
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 4, 4)
                self.install_flow(event, ip_packet, 5, selected_server, selected_mac, 2, 1)

            elif selected_server == S3:
                self.install_flow(event, ip_packet, in_port, selected_server, selected_mac, 3, 6)

                ip_packet.dstip = selected_server
                event.parsed.dst = selected_mac
                
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 2, 4)
                self.install_flow(event, ip_packet, 4, selected_server, selected_mac, 1, 3)

            elif selected_server == S4:
                self.install_flow(event, ip_packet, in_port, selected_server, selected_mac, 3, 6)

                ip_packet.dstip = selected_server
                event.parsed.dst = selected_mac
                
                self.install_flow(event, ip_packet, 3, selected_server, selected_mac, 2, 4)
                self.install_flow(event, ip_packet, 4, selected_server, selected_mac, 2, 3)

        

    def _handle_from_server(self, event, ip_packet, in_port, dpid):
        """ Handle packets returning from servers to clients."""
        src_ip = ip_packet.srcip
        dst_ip = ip_packet.dstip

        log.info(f"Switch S{event.dpid}: Modifying source IP from {src_ip} to VIP {VIP}")

        # Install flow for this path
        msg = of.ofp_flow_mod()
        match = of.ofp_match()

        match.in_port = in_port 
        match.dl_src = event.parsed.src  # Source MAC address
        match.dl_dst = event.parsed.dst  # Destination MAC address
        match.nw_src = ip_packet.srcip  # Source IP address
        match.nw_dst = ip_packet.dstip  # Destination IP address
        
        transport_packet = ip_packet.payload
        match.tp_src = transport_packet.srcport  # Source port
        match.tp_dst = transport_packet.dstport  # Destination port
    
        msg.match = match
        
        msg.actions.append(of.ofp_action_nw_addr.set_src(VIP))
        msg.actions.append(of.ofp_action_dl_addr.set_src(VMAC))

        if dpid == 5:
            if dst_ip == H5:
                msg.actions.append(of.ofp_action_output(port=1))
            elif dst_ip == H6:
                msg.actions.append(of.ofp_action_output(port=2))
                
        elif dpid == 6:
            if dst_ip == H7:
                msg.actions.append(of.ofp_action_output(port=1))
            elif dst_ip == H8:
                msg.actions.append(of.ofp_action_output(port=2))

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
