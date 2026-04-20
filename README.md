# SDN Real-Time Network Utilization Monitor

A high-performance Software-Defined Networking (SDN) application that provides real-time bandwidth monitoring and visualization across dynamic network topologies. Built using the **Ryu SDN Framework**, **Mininet**, and **OpenFlow 1.3**.

---

## 🚀 Key Features

- **Dynamic Topology Support**: Deploy linear switch chains of any size with customizable host counts via CLI.
- **Real-Time Mbps Calculation**: High-precision bandwidth throughput monitoring (RX/TX) using 3-second polling intervals.
- **Horizontal Terminal Dashboard**: Optimized CLI output showing multiple switch statistics side-by-side.
- **Obsidian Core Web Dashboard**: A modern, industrial-themed web interface for visual traffic monitoring.
- **L2 Learning Logic**: Fully functional MAC-learning switch implementation with proactive flow installation.

---

## 🛠️ Architecture

### Components
1. **Controller (`monitor_controller.py`)**: 
   - Managed by Ryu.
   - Handles `PacketIn` events for MAC learning.
   - Periodically polls `PortStats` to compute Mbps.
   - Exposes a REST API at `:8080/stats/utilization`.
2. **Topology (`topology.py`)**: 
   - Managed by Mininet.
   - Utilizes `TCLink` to enforce hardware-level bandwidth constraints (default: 10 Mbps).
3. **Web Interface (`dashboard.html`)**: 
   - Vanilla JS/CSS client that visualizes traffic through real-time gauges.

---

## 💻 Installation & Setup

### Prerequisites
- **Ubuntu 22.04** (Recommended)
- **Python 3.10+**
- **Mininet & Open vSwitch** installed (`sudo apt install mininet`)

### 1. Environment Configuration
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (specific versions required for Ryu stability)
pip install eventlet==0.33.3 dnspython==2.2.1 six webob msgpack-python routes tinyrpc ovs
pip install --no-deps "ryu @ git+https://github.com/faucetsdn/ryu.git"
```

---

## 🚦 Execution

### Step 1: Start the Ryu Controller
```bash
source .venv/bin/activate
ryu-manager monitor_controller.py
```

### Step 2: Launch the Topology
You can now define your network size at runtime:
```bash
# Example: 3 switches with 2 hosts each
sudo python3 topology.py --switches 3 --hosts 2
```

### Step 3: View the Dashboard
Simply open `dashboard.html` in your browser. It will automatically connect to the local controller.

---

## 🧪 Testing Scenarios

### Test Case 1: Scalability & Topology Verification
**Goal:** Verify that the dynamic topology correctly builds and that the terminal displays multiple switches horizontally.
1. **Launch:** `sudo python3 topology.py --switches 4 --hosts 8`
2. **Verification:** Confirm Mininet shows 4 switches (`s1-s4`) and 8 hosts (`h1-h8`). The Ryu terminal should display **4 tables** side-by-side.

### Test Case 2: Real-Time Bandwidth Accuracy
**Goal:** Confirm the Mbps calculation matches a known load.
1. **Launch:** `sudo python3 topology.py --switches 2 --hosts 4`
2. **Traffic:** 
   - Mininet: `h1 iperf -s &`
   - Mininet: `h2 iperf -c 10.0.0.1 -t 30 -u -b 5M` (Sends a 5 Mbps UDP stream).
3. **Expectation:** Both Terminal and Dashboard should show approximately **5.0 Mbps** for the corresponding ports.

### Test Case 3: Multi-Hop Bottleneck Analysis
**Goal:** Observe how traffic propagates through the switch chain.
1. **Launch:** `sudo python3 topology.py --switches 3 --hosts 6`
2. **Traffic:** 
   - Mininet: `h5 iperf -s &`
   - Mininet: `h1 iperf -c 10.0.0.5 -t 30`
3. **Expectation:** You should see activity on `s1` (Port 1), `s2` (backbone ports), and `s3` (Port 1/h5), demonstrating full network traversal.

### Test Case 4: Dashboard Stress Test
**Goal:** Ensure the web dashboard's visual indicators respond correctly to multiple simultaneous streams.
1. **Launch:** `sudo python3 topology.py --switches 2 --hosts 4`
2. **Traffic:** Start servers on `h3` and `h4`. Simultaneously run `h1 iperf -c h3 -b 4M` and `h2 iperf -c h4 -b 4M`.
3. **Expectation:** All active ports should pulse Cyan/Amber, and gauges should reflect the combined ~80% link utilization.

---

## 📜 Technical Specs
- **Protocol**: OpenFlow 1.3
- **Polling Interval**: 3.0 seconds
- **Default Bandwidth**: 10 Mbps per link
- **API Endpoint**: `GET /stats/utilization`
