#!/usr/bin/python3
"""
Custom Mininet topology for Network Utilization Monitoring.
Topology:
    h1 --- s1 --- s2 --- h3
    h2 ---/        \--- h4
All links are 10 Mbps.
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

class UtilizationTopo(Topo):
    def build(self):
        # 1. Add switches
        s1 = self.addSwitch('s1', dpid='0000000000000001')
        s2 = self.addSwitch('s2', dpid='0000000000000002')

        # 2. Add hosts with specific IP addresses
        h1 = self.addHost('h1', ip='10.0.0.1')
        h2 = self.addHost('h2', ip='10.0.0.2')
        h3 = self.addHost('h3', ip='10.0.0.3')
        h4 = self.addHost('h4', ip='10.0.0.4')

        # 3. Add links with 10 Mbps bandwidth
        # Connect hosts to switches
        self.addLink(h1, s1, cls=TCLink, bw=10)
        self.addLink(h2, s1, cls=TCLink, bw=10)
        self.addLink(h3, s2, cls=TCLink, bw=10)
        self.addLink(h4, s2, cls=TCLink, bw=10)

        # Connect switches together
        self.addLink(s1, s2, cls=TCLink, bw=10)

def run_topology():
    # Create the network
    topo = UtilizationTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
        switch=OVSSwitch,
        waitConnected=True
    )

    # Start the network
    net.start()

    # Force OpenFlow 1.3 on all switches using ovs-vsctl
    print("\n*** Configuring switches to use OpenFlow 1.3...")
    for sw in net.switches:
        sw.cmd(f'ovs-vsctl set bridge {sw.name} protocols=OpenFlow13')

    # Initial connectivity test to populate MAC tables
    print("\n*** Running pingall to initialize MAC learning...")
    net.pingAll()

    # Open the Mininet CLI
    print("\n*** Network is ready. Use 'iperf' to test bandwidth.")
    CLI(net)

    # Stop the network
    net.stop()

if __name__ == '__main__':
    # Set the log level to info to see Mininet output
    setLogLevel('info')
    run_topology()
