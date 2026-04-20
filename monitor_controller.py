# Ryu Controller for measuring real-time bandwidth utilization (Mbps).

# --- Python 3.10+ Compatibility Fixes ---
import collections
# Fix for AttributeError: module 'collections' has no attribute 'MutableMapping'
if not hasattr(collections, 'MutableMapping'):
    import collections.abc
    collections.MutableMapping = collections.abc.MutableMapping
# ----------------------------------------

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib import hub
from ryu.app.wsgi import WSGIApplication, ControllerBase, route
from webob import Response
import time
import json

# Define the REST API endpoint name
monitor_instance_name = 'monitor_api_app'
url = '/stats/utilization'

class NetworkUtilizationMonitor(app_manager.RyuApp):
    """
    Ryu Controller for measuring real-time bandwidth utilization (Mbps).
    Implements MAC learning switch logic and periodic port statistics polling.
    Includes a REST API for dashboard integration.
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(NetworkUtilizationMonitor, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.stats = {}  # Raw byte counts
        self.utilization = {}  # Calculated Mbps for REST API
        
        # Register the REST API controller
        wsgi = kwargs['wsgi']
        wsgi.register(MonitorRestController, {monitor_instance_name: self})
        
        # Spawn monitoring thread (3 second interval)
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        self.datapaths[datapath.id] = datapath
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port
        out_port = self.mac_to_port[dpid].get(dst, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.add_flow(datapath, 1, match, actions, idle_timeout=10, hard_timeout=30)
        data = None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(3)
            self._print_stats_side_by_side()

    def _request_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    def _print_stats_side_by_side(self):
        if not self.utilization:
            return

        dpids = sorted(self.utilization.keys())
        # Filter out switches that haven't reported yet
        active_dpids = [d for d in dpids if self.utilization[d]]
        if not active_dpids:
            return

        # Prepare headers
        header = ""
        sub_header = ""
        separator = ""
        col_width = 40

        for dpid in active_dpids:
            # Show last 4 digits of DPID for brevity in header
            header += f" [Switch {dpid[-4:]}]".ljust(col_width)
            sub_header += f"{'Port':<8} {'RX (Mbps)':<12} {'TX (Mbps)':<12}".ljust(col_width)
            separator += ("-" * 35).ljust(col_width)

        print("\n" + header)
        print(sub_header)
        print(separator)

        # Collect all port numbers for each switch to iterate through rows
        switch_ports = {d: sorted(self.utilization[d].keys(), key=int) for d in active_dpids}
        max_ports = max(len(ports) for ports in switch_ports.values())

        for i in range(max_ports):
            row = ""
            for dpid in active_dpids:
                ports = switch_ports[dpid]
                if i < len(ports):
                    p_no = ports[i]
                    stats = self.utilization[dpid][p_no]
                    rx, tx = stats['rx'], stats['tx']
                    row += f"{p_no:<8} {rx:<12.4f} {tx:<12.4f}".ljust(col_width)
                else:
                    row += "".ljust(col_width)
            print(row)
        print(separator)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        dpid_str = f"{dpid:016x}"
        
        self.utilization.setdefault(dpid_str, {})
        
        for stat in sorted(body, key=lambda attr: attr.port_no):
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
                rx_mbps = (curr_rx_bytes - prev_rx_bytes) * 8 / (delta_time * 1e6)
                tx_mbps = (curr_tx_bytes - prev_tx_bytes) * 8 / (delta_time * 1e6)
                
                # Store for REST API and terminal display
                self.utilization[dpid_str][str(port_no)] = {
                    'rx': round(rx_mbps, 4),
                    'tx': round(tx_mbps, 4)
                }
            else:
                self.utilization[dpid_str][str(port_no)] = {'rx': 0, 'tx': 0}

            self.stats[key] = (curr_rx_bytes, curr_tx_bytes, curr_time)

class MonitorRestController(ControllerBase):
    """
    REST API Controller to expose utilization stats.
    """
    def __init__(self, req, link, data, **config):
        super(MonitorRestController, self).__init__(req, link, data, **config)
        self.monitor_app = data[monitor_instance_name]

    @route('monitor', url, methods=['GET'])
    def list_utilization(self, req, **kwargs):
        """
        Returns utilization stats for all switches as JSON.
        """
        # Encode string to bytes to avoid "text value without a charset" error
        body = json.dumps(self.monitor_app.utilization).encode('utf-8')
        return Response(content_type='application/json', body=body, 
                        headerlist=[('Access-Control-Allow-Origin', '*')])
