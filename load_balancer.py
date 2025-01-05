from pox.core import core
from pox.openflow import *
from pox.lib.packet import *
import hashlib
import networkx as nx  # Biblioteka do grafów

log = core.getLogger()

class LoadBalancer (object):
    def __init__(self):
        core.openflow.addListenerByName("ConnectionUp", self._handle_ConnectionUp)
        core.openflow.addListenerByName("PacketIn", self._handle_PacketIn)
        self.graph = nx.Graph()  # Tworzymy graf do przechowywania topologii sieci

    def _handle_ConnectionUp(self, event):
        """
        Kiedy przełącznik się łączy, aktualizujemy graf i instalujemy przepływy.
        """
        log.info("Połączono z przełącznikiem: %s", event.dpid)

        # Wstępnie dodajemy przełącznik do grafu
        self.graph.add_node(event.dpid)

        # Aktualizacja topologii przełączników i portów (powinna być rozbudowana)
        for port in event.connection.ports.values():
            self.graph.add_edge(event.dpid, port)

        # Oblicz najkrótsze ścieżki po dodaniu wszystkich połączeń
        self._calculate_shortest_paths(event.connection)

    def _handle_PacketIn(self, event):
        """
        Obsługuje pakiety przychodzące do kontrolera.
        """
        packet = event.parsed

        src_ip = packet.payload.srcip
        dst_ip = packet.payload.dstip

        # Obliczamy hash na podstawie adresu IP
        hash_value = self._hash_ip(src_ip, dst_ip)

        # Wybieramy najkrótszą ścieżkę na podstawie hash'a
        shortest_path = self._select_shortest_path(src_ip, dst_ip, hash_value)

        # Instalujemy odpowiedni przepływ dla tej ścieżki
        self._install_flow(event.connection, shortest_path, packet)

    def _hash_ip(self, src_ip, dst_ip):
        """
        Funkcja oblicza hash na podstawie adresu IP.
        """
        combined_ip = str(src_ip) + str(dst_ip)
        hash_value = hashlib.md5(combined_ip.encode()).hexdigest()
        return int(hash_value, 16)

    def _select_shortest_path(self, src_ip, dst_ip, hash_value):
        """
        Wybieramy najkrótszą ścieżkę na podstawie hash'a.
        """
        # Tu powinniśmy mieć algorytm do obliczania najkrótszych ścieżek
        # W tym przypadku korzystamy z NetworkX (Python Graph Library)
        shortest_paths = nx.shortest_path(self.graph, source=src_ip, target=dst_ip)

        # Wybieramy ścieżkę na podstawie wartości hash'a
        path_index = hash_value % len(shortest_paths)
        return shortest_paths[path_index]

    def _install_flow(self, connection, path, packet):
        """
        Instalujemy przepływ na przełączniku dla wybranej ścieżki
        """
        match = ofp_match()
        match.dl_type = packet.type
        match.nw_src = packet.payload.srcip
        match.nw_dst = packet.payload.dstip

        # Instalacja przepływu w OpenFlow
        flow_mod = ofp_flow_mod()
        flow_mod.match = match
        for switch in path:
            flow_mod.actions.append(ofp_action_output(port=switch))
        connection.send(flow_mod)
        log.info("Zainstalowano przepływ: %s -> %s, ścieżka: %s", packet.payload.srcip, packet.payload.dstip, path)

def launch():
    """
    Funkcja startowa kontrolera POX
    """
    core.registerNew(LoadBalancer)
