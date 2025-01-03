from pox.core import core
import pox.openflow.libopenflow_01 as of
import hashlib

log = core.getLogger()

class HashLoadBalancer(object):
    def __init__(self, connection):
        self.connection = connection
        connection.addListeners(self)

    def _handle_PacketIn(self, event):
        packet = event.parsed

        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        ip = packet.find('ipv4')
        if not ip:
            log.info("Non-IPv4 packet received; ignoring")
            return

        # Oblicz hash na podstawie adresu źródłowego
        src_ip = ip.srcip.toStr()
        hash_value = int(hashlib.md5(src_ip.encode()).hexdigest(), 16)
        
        # Lista dostępnych portów na przełączniku
        available_ports = [p.port_no for p in self.connection.features.ports if p.port_no != event.port and p.port_no < of.OFPP_MAX]

        if not available_ports:
            log.warning(f"No available ports to forward the packet for {src_ip}")
            return

        # Wybierz port na podstawie hash
        selected_port = available_ports[hash_value % len(available_ports)]

        # Instalacja reguły przepływu
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.actions.append(of.ofp_action_output(port=selected_port))
        self.connection.send(msg)

        # Wysłanie pakietu natychmiast
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=selected_port))
        self.connection.send(msg)

class HashLoadBalancerController(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.info(f"Switch {event.connection.dpid} connected")
        HashLoadBalancer(event.connection)

def launch():
    core.registerNew(HashLoadBalancerController)
