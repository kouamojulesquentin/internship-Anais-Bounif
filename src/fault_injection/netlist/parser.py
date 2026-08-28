from fault_injection.models.circuit import Circuit, SubCircuit
from fault_injection.models.component import Component


class NetlistParser(object):
    def parse_file(self, path):
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            text = handle.read()
        circuit = self.parse_text(text)
        circuit.source_path = path
        return circuit

    def parse_text(self, text):
        circuit = Circuit()
        current_subckt = None

        for start_line, end_line, logical_text in self._logical_lines(text):
            stripped = logical_text.strip()
            if not stripped:
                continue

            low = stripped.lower()

            if low.startswith('.subckt'):
                tokens = self._normalize_syntax(stripped).split()
                if len(tokens) < 2:
                    continue
                current_subckt = SubCircuit(tokens[1], tokens[2:])
                circuit.add_subcircuit(current_subckt)
                continue

            if low.startswith('.ends'):
                current_subckt = None
                continue

            if stripped.startswith('.') or current_subckt is None:
                continue

            component = self._parse_component(
                logical_text, start_line, end_line, current_subckt.name
            )
            if component is not None:
                current_subckt.add_component(component)

        return circuit

    def _logical_lines(self, text):
        result = []
        current_parts = []
        start_line = None
        end_line = None

        for index, raw in enumerate(text.splitlines(), 1):
            line = raw.rstrip()

            if not line.strip():
                continue
            if line.lstrip().startswith('*'):
                continue

            if line.lstrip().startswith('+'):
                if current_parts:
                    current_parts.append(line.lstrip()[1:].strip())
                    end_line = index
                continue

            if current_parts:
                result.append((start_line, end_line, ' '.join(current_parts)))

            current_parts = [line.strip()]
            start_line = index
            end_line = index

        if current_parts:
            result.append((start_line, end_line, ' '.join(current_parts)))

        return result

    def _normalize_syntax(self, line):
        # Support V1 des syntaxes Spectre: M1 (d g s b) model ...
        line = line.replace('(', ' ').replace(')', ' ')
        return ' '.join(line.split())

    def _parse_component(self, logical_text, start_line, end_line, subckt_name):
        normalized = self._normalize_syntax(logical_text)
        tokens = normalized.split()
        if len(tokens) < 2:
            return None

        name = tokens[0]
        prefix = name[0].lower()
        params = {}
        positional = []

        for token in tokens[1:]:
            if '=' in token:
                key, value = token.split('=', 1)
                params[key.upper()] = value
            else:
                positional.append(token)

        ctype = self._component_type(prefix)
        nodes = []
        model = None

        if ctype == 'mosfet':
            nodes = positional[:4]
            model = positional[4] if len(positional) >= 5 else None

        elif ctype == 'bjt':
            if len(positional) >= 5:
                nodes = positional[:4]  # C B E substrate
                model = positional[4]
            elif len(positional) >= 4:
                nodes = positional[:3]
                model = positional[3]

        elif ctype == 'subckt':
            if positional:
                nodes = positional[:-1]
                model = positional[-1]

        elif ctype in ('resistor', 'capacitor', 'inductor', 'diode'):
            nodes = positional[:2]
            model = positional[2] if len(positional) >= 3 else None

        else:
            if positional:
                nodes = positional[:-1]
                model = positional[-1]

        if ctype == 'subckt' and model:
            primitive_type = self._primitive_type(model)
            if primitive_type is not None:
                ctype = primitive_type

        return Component(
            name=name, component_type=ctype, nodes=nodes, model=model,
            parameters=params, raw_text=normalized, start_line=start_line,
            end_line=end_line, subckt_name=subckt_name
        )

    def _component_type(self, prefix):
        return {
            'm': 'mosfet', 'q': 'bjt', 'r': 'resistor', 'c': 'capacitor',
            'l': 'inductor', 'd': 'diode', 'x': 'subckt',
            'v': 'voltage_source', 'i': 'current_source'
        }.get(prefix, 'unknown')

    def _primitive_type(self, model):
        low = model.lower()
        if 'rpoly' in low or 'rdiff' in low:
            return 'resistor'
        if 'cpoly' in low or low.startswith('primitive_c'):
            return 'capacitor'
        if low in ('primitive_nd', 'primitive_nwd', 'primitive_pd'):
            return 'diode'
        if 'ind' in low or 'coil' in low:
            return 'inductor'
        return None
