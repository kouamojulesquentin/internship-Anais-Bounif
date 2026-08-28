class Component(object):
    def __init__(self, name, component_type, nodes, model=None, parameters=None,
                 raw_text='', start_line=None, end_line=None, subckt_name=None):
        self.name = name
        self.component_type = component_type
        self.nodes = list(nodes)
        self.model = model
        self.parameters = parameters or {}
        self.raw_text = raw_text
        self.start_line = start_line
        self.end_line = end_line
        self.subckt_name = subckt_name

    def to_dict(self):
        return {
            'name': self.name, 'component_type': self.component_type,
            'nodes': list(self.nodes), 'model': self.model,
            'parameters': dict(self.parameters), 'raw_text': self.raw_text,
            'start_line': self.start_line, 'end_line': self.end_line,
            'subckt_name': self.subckt_name
        }
