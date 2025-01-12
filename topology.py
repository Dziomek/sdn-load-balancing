# -*- coding: utf-8 -*-


from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel
from mininet.cli import CLI
import threading
import random
import time

class CustomTopo(Topo):
    def build(self):
        # hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')
        h5 = self.addHost('h5')
        h6 = self.addHost('h6')
        h7 = self.addHost('h7')
        h8 = self.addHost('h8')
        vip_host = self.addHost('vip_host')

        # switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')
        s5 = self.addSwitch('s5')
        s6 = self.addSwitch('s6')

        #connections vip_host - edge_switch
        self.addLink(vip_host, s1)
        self.addLink(vip_host, s3)
        self.addLink(vip_host, s5)
        self.addLink(vip_host, s6)

        # connections switch-host
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s3)
        self.addLink(h4, s3)
        self.addLink(h5, s5)
        self.addLink(h6, s5)
        self.addLink(h7, s6)
        self.addLink(h8, s6)

        # connections switch-switch
        self.addLink(s1, s2)
        self.addLink(s1, s3)
        self.addLink(s2, s4)
        self.addLink(s3, s4)
        self.addLink(s2, s5)
        self.addLink(s4, s6)
        self.addLink(s1, s4)
        self.addLink(s2, s3)


def generate_traffic(host, vip):
    """
    Funkcja generuje ruch z podanego hosta do VIP.
    """
    host.cmd('iperf -s &')

    time.sleep(15)

    while True:
        traffic_duration = random.randint(1, 15)

        # Wysyłanie ruchu do VIP
        host.cmd('iperf -c {} -t {} &'.format(vip, traffic_duration))        
        time.sleep(traffic_duration)

        # Losowa przerwa przed wygenerowaniem kolejnego ruchu
        wait_time = random.randint(1, 15)
        time.sleep(wait_time)


def run():
    topo = CustomTopo()
    net = Mininet(topo=topo, controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633))
    net.start()

    vip = '10.0.0.100'  # Wirtualny adres IP
    hosts = [net.get('h{}'.format(i)) for i in range(1, 9)]

    clients = hosts[4:]  # h5-h8 jako klienci

    vip_host = net.get('vip_host')
    vip_host.cmd('ifconfig vip_host-eth0 {} netmask 255.255.255.0 up'.format(vip))

    # Uruchamianie generowania ruchu tylko na hostach-klientach
    for host in clients:
        t = threading.Thread(target=generate_traffic, args=(host, vip))
        t.setDaemon(True)
        t.start()

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
