# -*- coding: utf-8 -*-


from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel
from mininet.cli import CLI

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

def run():
    topo = CustomTopo()
    net = Mininet(topo=topo, controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633))
    net.start()

    h2 = net.get('h2')
    h2.popen('iperf -s &')


    h1 = net.get('h1')
    h1.popen('iperf -c {} -t 0 -i 1 &'.format(h2.IP()))

    print("Running iperf test between h1 and h2...")
    
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
