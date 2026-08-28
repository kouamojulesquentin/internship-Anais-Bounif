class SubCircuit(object):
    def __init__(self, name, ports):
        self.name = name
        self.ports = list(ports)
        self.components = []

    def add_component(self, component):
        self.components.append(component)


class Circuit(object):
    def __init__(self, source_path=None):
        self.source_path = source_path
        self.subcircuits = {}

    def add_subcircuit(self, subckt):
        self.subcircuits[subckt.name] = subckt

    def all_components(self):
        result = []
        for subckt in self.subcircuits.values():
            result.extend(subckt.components)
        return result
