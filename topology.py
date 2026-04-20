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
    def build(self, n_switches=2, n_hosts=4):
        """
        Builds a linear topology of switches, distributing a total number of hosts
        across them. All links are constrained to 10 Mbps.
        """
        switches = []
        host_count = 1
        
        # Calculate how many hosts to put on each switch
        hosts_per_sw = n_hosts // n_switches
        extra_hosts = n_hosts % n_switches

        for i in range(1, n_switches + 1):
            # 1. Add switch
            dpid = f"{i:016x}"
            sw = self.addSwitch(f's{i}', dpid=dpid)
            
            # 2. Determine number of hosts for this specific switch
            current_sw_hosts = hosts_per_sw + (1 if i <= extra_hosts else 0)
            
            for _ in range(current_sw_hosts):
                h = self.addHost(f'h{host_count}', ip=f'10.0.0.{host_count}')
                self.addLink(h, sw, cls=TCLink, bw=10)
                host_count += 1
            
            # 3. Connect to previous switch in linear chain
            if switches:
                self.addLink(sw, switches[-1], cls=TCLink, bw=10)
            
            switches.append(sw)

def run_topology(n_switches, n_hosts):
    # Create the network
    topo = UtilizationTopo(n_switches=n_switches, n_hosts=n_hosts)
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
    print(f"\n*** Network ready ({n_switches} switches, {n_hosts} hosts).")
    CLI(net)

    # Stop the network
    net.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dynamic SDN Topology for Utilization Monitoring')
    parser.add_argument('--switches', type=int, default=2, help='Number of switches in linear chain (default: 2)')
    parser.add_argument('--hosts', type=int, default=4, help='Total number of hosts in the network (default: 4)')
    args = parser.parse_args()

    setLogLevel('info')
    run_topology(n_switches=args.switches, n_hosts=args.hosts)
