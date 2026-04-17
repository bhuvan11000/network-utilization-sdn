# Project #19: Network Utilization Monitor (SDN)

## Problem Statement
Implement an SDN-based network monitor that calculates and displays real-time bandwidth utilization (in Mbps) across all active ports of OpenFlow 1.3 switches. The controller periodically polls each switch for port byte counters and computes throughput based on the delta between consecutive polls.

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

## Setup and Environment (Critical)
This project is optimized for **Ubuntu 22.04** and **Python 3.10**. Standard Ryu has compatibility issues with newer versions of `eventlet` and `dnspython`. Follow these exact steps to ensure a working environment.

### 1. Create the Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Manual Installation Strategy
Due to dependency conflicts in the standard Ryu distribution, use the following manual installation sequence:
```bash
# Uninstall any existing conflicting versions
pip uninstall -y ryu eventlet dnspython

# Install working underlying dependencies
pip install eventlet==0.33.3 dnspython==2.2.1 six webob msgpack-python routes tinyrpc ovs

# Install the patched Faucet SDN Ryu fork (ignores dependency checks)
pip install --no-deps "ryu @ git+https://github.com/faucetsdn/ryu.git"
```

## Execution Steps

### Terminal 1: Start the Ryu Controller
```bash
source .venv/bin/activate
ryu-manager monitor_controller.py
```

### Terminal 2: Start the Mininet Topology
```bash
# Note: Do NOT run this inside the venv. Use system Python.
sudo python3 topology.py
```

## Web Dashboard (Obsidian Core)
This project includes a real-time web interface built with vanilla JS and CSS.

### Accessing the Dashboard
1. Ensure the Ryu controller is running (`ryu-manager monitor_controller.py`).
2. Open the `dashboard.html` file directly in any modern web browser.
3. The dashboard will automatically connect to `http://localhost:8080/stats/utilization` and update every 3 seconds.

### Dashboard Features
- **Switch Cards**: Each switch is displayed as a separate industrial-style card.
- **Real-time Gauges**: Visual progress bars show bandwidth utilization relative to the 10 Mbps link limit.
- **Dynamic Indicators**: Active ports pulse with Electric Cyan (RX) or Solar Amber (TX) highlights when traffic is detected.

## Test Scenarios

### Scenario 1: Idle State vs. Single Stream
1. Verify the controller table shows `0.0000 Mbps` for all ports.
2. In Mininet CLI: `h3 iperf -s &`
3. In Mininet CLI: `h1 iperf -c 10.0.0.3 -t 20`
4. **Observation**: Port utilization should jump to ~9.4 Mbps in the controller terminal.

### Scenario 2: Shared Link Bottleneck
1. In Mininet CLI: `h3 iperf -s &` and `h4 iperf -s &`
2. Run simultaneous tests:
   - `h1 iperf -c 10.0.0.3 -t 30 &`
   - `h2 iperf -c 10.0.0.4 -t 30 &`
3. **Observation**: Since the `s1-s2` link is shared (10 Mbps total), both streams will show reduced bandwidth (approx 4-5 Mbps each) in the utilization table.

## Validation Commands
- **Check Flows**: `sudo ovs-ofctl -O OpenFlow13 dump-flows s1`
- **Check MACs**: `mininet> pingall`
- **Switch Config**: `sudo ovs-vsctl show`

## Rubric Mapping
- **Match-action**: `add_flow` method in `monitor_controller.py`
- **MAC Learning**: `_packet_in_handler` in `monitor_controller.py`
- **Polling Loop**: `hub.spawn` in `__init__`
- **Mbps Math**: `_port_stats_reply_handler` using 3s delta time.
- **TCLink**: `UtilizationTopo` class in `topology.py`.
