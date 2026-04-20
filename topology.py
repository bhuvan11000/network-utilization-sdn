#!/usr/bin/python3
"""
Custom Mininet topology for Network Utilization Monitoring.
Topology:
    h1 --- s1 --- s2 --- h3
    h2 ---/        \--- h4
All links are 10 Mbps.
"""

import argparse
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

class UtilizationTopo(Topo):
    def build(self, n_switches=2, hosts_per_switch=2):
        """
        Builds a linear topology of switches, each with a fixed number of hosts.
        All links are constrained to 10 Mbps.
        """
        switches = []
        host_count = 1

        for i in range(1, n_switches + 1):
            # 1. Add switch
            dpid = f"{i:016x}"
            sw = self.addSwitch(f's{i}', dpid=dpid)
            
            # 2. Add hosts for this switch
            for _ in range(hosts_per_switch):
                h = self.addHost(f'h{host_count}', ip=f'10.0.0.{host_count}')
                self.addLink(h, sw, cls=TCLink, bw=10)
                host_count += 1
            
            # 3. Connect to previous switch in linear chain
            if switches:
                self.addLink(sw, switches[-1], cls=TCLink, bw=10)
            
            switches.append(sw)

def run_topology(n_switches, hosts_per_switch):
    # Create the network
    topo = UtilizationTopo(n_switches=n_switches, hosts_per_switch=hosts_per_switch)
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
        switch=OVSSwitch,
        waitConnected=True
    )

    # Start the network
    net.start()

    # Force OpenFlow 1.3 on all switches
    print(f"\n*** Configuring {len(net.switches)} switches to use OpenFlow 1.3...")
    for sw in net.switches:
        sw.cmd(f'ovs-vsctl set bridge {sw.name} protocols=OpenFlow13')

    # Initial connectivity test to populate MAC tables
    print("\n*** Running pingall to initialize MAC learning...")
    net.pingAll()

    # Open the Mininet CLI
    print(f"\n*** Network ready ({n_switches} switches, {n_switches * hosts_per_switch} hosts).")
    CLI(net)

    # Stop the network
    net.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dynamic SDN Topology for Utilization Monitoring')
    parser.add_argument('--switches', type=int, default=2, help='Number of switches in linear chain (default: 2)')
    parser.add_argument('--hosts', type=int, default=2, help='Hosts per switch (default: 2)')
    args = parser.parse_args()

    setLogLevel('info')
    run_topology(n_switches=args.switches, hosts_per_switch=args.hosts)
