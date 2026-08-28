class Fault(object):
    def __init__(self, fault_id, fault_type, subtype, component_name,
                 terminals, nodes, weight=1.0, subckt_name=None, metadata=None):
        self.fault_id = fault_id
        self.fault_type = fault_type
        self.subtype = subtype
        self.component_name = component_name
        self.terminals = list(terminals)
        self.nodes = list(nodes)
        self.weight = float(weight)
        self.subckt_name = subckt_name
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            'fault_id': self.fault_id,
            'fault_type': self.fault_type,
            'subtype': self.subtype,
            'component_name': self.component_name,
            'terminals': ','.join(self.terminals),
            'nodes': ','.join(self.nodes),
            'weight': self.weight,
            'subckt_name': self.subckt_name or '',
            'metadata': str(self.metadata)
        }
