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
        h1 = self.addHost('h1', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', mac='00:00:00:00:00:04')
        h5 = self.addHost('h5', mac='00:00:00:00:00:05')
        h6 = self.addHost('h6', mac='00:00:00:00:00:06')
        h7 = self.addHost('h7', mac='00:00:00:00:00:07')
        h8 = self.addHost('h8', mac='00:00:00:00:00:08')

        # virtual host
        h9 = self.addHost('h9', mac='00:00:00:00:00:09')

        # switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')
        s5 = self.addSwitch('s5')
        s6 = self.addSwitch('s6')

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

        # virtual connection
        self.addLink(s2, h9)


def generate_traffic(host):    
    while True:
        traffic_duration = random.randint(1, 15)
        
        target_host = '10.0.0.9'
        print(f"Running iperf with target host: {target_host}")
        host.cmd('iperf -c ' + target_host + ' -t ' + str(traffic_duration) + ' &')

        time.sleep(traffic_duration)

        wait_time = random.randint(1, 15)
        time.sleep(wait_time)

def run():
    topo = CustomTopo()
    net = Mininet(topo=topo, controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633))
    net.start()
    

    # Uruchomienie serwerów
    for i in range(1,5):
        host = net.get('h' + str(i))
        host.cmd('iperf -s &')

    # Generowanie ruchu
    for i in range(5,9):
        host = net.get('h' + str(i))
        t = threading.Thread(target=generate_traffic, args=(host,))
        t.setDaemon(True)
        t.start()
    
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
