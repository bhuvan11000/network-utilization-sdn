# Project #19: Network Utilization Monitor (SDN)

## Problem Statement
The goal of this project is to implement an SDN-based network monitor that calculates and displays real-time bandwidth utilization (in Mbps) across all active ports of OpenFlow 1.3 switches. This requires the controller to periodically poll each switch for port byte counters and compute the throughput based on the difference (delta) between consecutive polls.

## Topology Diagram (ASCII)
```text
           (SDN Controller: Ryu)
                  |
         [Switch s1]-------[Switch s2]
          /      \          /      \
      [h1]      [h2]      [h3]      [h4]
    10.0.0.1  10.0.0.2  10.0.0.3  10.0.0.4

* All links use TCLink with bw=10 (10 Mbps)
```

## Setup and Execution
Follow these steps to run the project on Ubuntu 22.04.

### Step 1: Start the Ryu Controller
Open a terminal and activate the Python virtual environment:
```bash
source venv/bin/activate
ryu-manager monitor_controller.py
```

### Step 2: Start the Mininet Topology
Open a **second terminal** and run the topology script with `sudo`:
```bash
sudo python3 topology.py
```

## Expected Output
Once both are running, the controller will display a utilization table every 5 seconds.

### Sample Controller Output (during iperf test)
```text
[Switch 0000000000000001] Utilization Table (Interval: 5s)
Port     RX (Mbps)    TX (Mbps)   
-----------------------------------
1        9.4102       0.1245      
2        0.0000       0.0000      
3        0.1245       9.4102      
-----------------------------------
```

## Test Scenarios

### Scenario 1: Single Stream Traffic (Idle vs Active)
1. In the Mininet CLI, verify the utilization is near 0.0 Mbps.
2. Start an iperf server on `h3`: `h3 iperf -s &`
3. Start an iperf client on `h1` to send traffic for 20 seconds: `h1 iperf -c 10.0.0.3 -t 20`
4. **Observation:** The controller table should show ~9.4 Mbps utilization on the active ports during the test.

### Scenario 2: Multiple Simultaneous Streams
1. Start servers on `h1` and `h2`:
   - `h1 iperf -s &`
   - `h2 iperf -s &`
2. Start simultaneous clients from `h3` and `h4`:
   - `h3 iperf -c 10.0.0.1 -t 30 &`
   - `h4 iperf -c 10.0.0.2 -t 30 &`
3. **Observation:** Since the link between `s1` and `s2` is shared (10 Mbps), both streams will compete for bandwidth, showing approximately 4.5-5.0 Mbps each in the utilization table.

## Validation Commands
Inside the Mininet CLI or a separate terminal:
- **Pingall:** `mininet> pingall`
- **Iperf:** `mininet> h1 iperf -c h3`
- **Dump Flows:** `sudo ovs-ofctl -O OpenFlow13 dump-flows s1`

## Rubric Implementation Mapping
| Rubric Component | Implementation Location |
| :--- | :--- |
| Mininet + Ryu (OF 1.3) | `topology.py` + `monitor_controller.py` |
| Match-action (OFPFlowMod) | `monitor_controller.py` in `add_flow` |
| MAC Learning (PacketIn) | `monitor_controller.py` in `_packet_in_handler` |
| Periodic Polling | `monitor_controller.py` in `hub.spawn` and `_monitor` |
| Mbps Calculation | `monitor_controller.py` in `_port_stats_reply_handler` |
| Utilization Table (5s) | `monitor_controller.py` in `_port_stats_reply_handler` |
| TCLink 10 Mbps | `topology.py` in `UtilizationTopo.build` |
| Force OF 1.3 | `topology.py` in `run_topology` using `ovs-vsctl` |

## References
1. Ryu Documentation: [https://ryu.readthedocs.io/](https://ryu.readthedocs.io/)
2. Mininet Python API: [http://mininet.org/api/](http://mininet.org/api/)
3. OpenFlow Switch Specification v1.3.0
