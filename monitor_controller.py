from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib import hub
import time

class NetworkUtilizationMonitor(app_manager.RyuApp):
    """
    Ryu Controller for measuring real-time bandwidth utilization (Mbps).
    Implements MAC learning switch logic and periodic port statistics polling.
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkUtilizationMonitor, self).__init__(*args, **kwargs)
        # mac_to_port[dpid][mac_address] = port
        self.mac_to_port = {}
        # Keep track of active datapaths for monitoring
        self.datapaths = {}
        # Store previous stats: (dpid, port_no) -> (rx_bytes, tx_bytes, timestamp)
        self.stats = {}
        # Spawn a background thread for periodic polling
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Installs the table-miss flow rule and registers the datapath.
        """
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Register datapath for monitoring
        self.datapaths[datapath.id] = datapath

        # Install table-miss flow entry (Priority 0)
        # Match anything, send to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=0, hard_timeout=0):
        """
        Helper method to install flow rules on a switch.
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, idle_timeout=idle_timeout,
                                    hard_timeout=hard_timeout)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst,
                                    idle_timeout=idle_timeout,
                                    hard_timeout=hard_timeout)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        Handles Packet-In events. Implements MAC learning and flow installation.
        """
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP packets used for topology discovery
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})

        # Learn the source MAC and its port
        self.mac_to_port[dpid][src] = in_port

        # Determine output port based on learned MACs
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # If destination is known, install a flow to handle future packets in hardware
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            # idle_timeout: rule removed if no traffic for 10s
            # hard_timeout: rule removed after 30s regardless of traffic
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id, 
                              idle_timeout=10, hard_timeout=30)
                return
            else:
                self.add_flow(datapath, 1, match, actions, 
                              idle_timeout=10, hard_timeout=30)
        
        # Send Packet-Out to the switch
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _monitor(self):
        """
        Infinite loop to poll every switch for port statistics every 5 seconds.
        """
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(5)

    def _request_stats(self, datapath):
        """
        Sends an OFPPortStatsRequest to the switch.
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """
        Calculates and displays real-time bandwidth utilization upon receiving stats.
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        
        # Display header for the utilization table
        print(f"\n[Switch {dpid:016x}] Utilization Table (Interval: 5s)")
        print(f"{'Port':<8} {'RX (Mbps)':<12} {'TX (Mbps)':<12}")
        print("-" * 35)

        for stat in sorted(body, key=lambda attr: attr.port_no):
            # Skip the LOCAL port (internal to OVS)
            if stat.port_no == ev.msg.datapath.ofproto.OFPP_LOCAL:
                continue

            port_no = stat.port_no
            curr_rx_bytes = stat.rx_bytes
            curr_tx_bytes = stat.tx_bytes
            curr_time = time.time()

            key = (dpid, port_no)
            if key in self.stats:
                prev_rx_bytes, prev_tx_bytes, prev_time = self.stats[key]
                delta_time = curr_time - prev_time
                
                # Utilization formula: (delta_bytes * 8 bits) / (delta_time * 1,000,000) = Mbps
                rx_mbps = (curr_rx_bytes - prev_rx_bytes) * 8 / (delta_time * 1e6)
                tx_mbps = (curr_tx_bytes - prev_tx_bytes) * 8 / (delta_time * 1e6)

                print(f"{port_no:<8} {rx_mbps:<12.4f} {tx_mbps:<12.4f}")
            else:
                # First poll, can't calculate delta yet
                print(f"{port_no:<8} {'Initializing':<12} {'Initializing':<12}")

            # Store current values for the next calculation
            self.stats[key] = (curr_rx_bytes, curr_tx_bytes, curr_time)
        print("-" * 35)
