import os
import re

from fault_injection.spice_utils import parse_spice_value, format_spice_value, SpiceValueError

OPEN_GATE_MODEL = (
    '* Open gate model\n'
    '.subckt open_gate_model d2 g2 s2\n'
    'R1 d2 n_inter 0.5T\n'
    'R2 s2 n_inter 0.5T\n'
    'R3 n_inter g2 1T\n'
    '.ends open_gate_model\n'
)


class FaultInjectionError(Exception):
    pass


class NetlistInjector(object):
    def __init__(self, config):
        self.short_cfg = config['short_model']
        self.open_cfg = config['open_model']

    def inject_file(self, source_path, circuit, fault, output_path):
        component = self._find_component(circuit, fault)
        if component is None:
            raise FaultInjectionError('Composant introuvable: {}'.format(fault.component_name))

        with open(source_path, 'r', encoding='utf-8', errors='replace') as handle:
            lines = handle.readlines()

        start = component.start_line - 1
        end = component.end_line
        replacement, extra_lines = self._build_injection(component, fault)

        block = [replacement + '\n'] + [line + '\n' for line in extra_lines]
        # Remplace toute la plage originale, y compris les lignes de continuation '+'.
        lines[start:end] = block

        text = ''.join(lines)

        if fault.subtype == 'G_OPEN' and '.subckt open_gate_model' not in text.lower():
            text += '\n' + OPEN_GATE_MODEL

        folder = os.path.dirname(output_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        with open(output_path, 'w', encoding='utf-8', errors='replace') as handle:
            handle.write(text)

        return output_path

    def _build_injection(self, c, fault):
        if fault.fault_type == 'SHORT':
            extra = self._short_element('xr_fault', fault.nodes[0], fault.nodes[1])
            return c.raw_text, [extra]

        if fault.fault_type == 'PARAMETRIC':
            return self._apply_parametric(c, fault)

        if fault.fault_type != 'OPEN':
            raise FaultInjectionError('Type non supporte: {}'.format(fault.fault_type))

        if c.component_type == 'mosfet':
            return self._mos_open(c, fault)
        if c.component_type == 'bjt':
            return self._bjt_open(c, fault)
        return self._two_terminal_open(c)

    def _two_terminal_open(self, c):
        old_node = c.nodes[0]
        new_node = '__open_{}_1'.format(self._safe(c.name))
        changed = self._replace_node(c.raw_text, 0, new_node)
        return changed, [self._open_element('xr_fault', old_node, new_node)]

    def _bjt_open(self, c, fault):
        positions = {'C':0, 'B':1, 'E':2}
        terminal = fault.terminals[0]
        pos = positions[terminal]
        old_node = c.nodes[pos]
        new_node = '__open_{}_{}'.format(self._safe(c.name), terminal.lower())
        changed = self._replace_node(c.raw_text, pos, new_node)
        return changed, [self._open_element('xr_fault', old_node, new_node)]

    def _mos_open(self, c, fault):
        terminal = fault.terminals[0]
        positions = {'D':0, 'G':1, 'S':2, 'B':3}

        if terminal == 'G':
            drain, source = c.nodes[0], c.nodes[2]
            new_gate = '__gate_open_{}'.format(self._safe(c.name))
            changed = self._replace_node(c.raw_text, 1, new_gate)
            xline = 'XOG_{} {} {} {} open_gate_model'.format(
                self._safe(c.name), drain, new_gate, source
            )
            return changed, [xline]

        pos = positions[terminal]
        old_node = c.nodes[pos]
        new_node = '__open_{}_{}'.format(self._safe(c.name), terminal.lower())
        changed = self._replace_node(c.raw_text, pos, new_node)
        return changed, [self._open_element('xr_fault', old_node, new_node)]

    def _short_element(self, name, n1, n2):
        c = self.short_cfg
        if 'primitive' in c:
            return '{} {} {} {} L={} W={} M={}'.format(
                name, n1, n2, c['primitive'], c['L'], c['W'], c['M']
            )
        # Mode generique (sans PDK/fonderie specifique): resistance ideale SPICE.
        return 'R_{} {} {} {}'.format(name, n1, n2, c['value'])

    def _open_element(self, name, n1, n2):
        c = self.open_cfg
        if 'primitive' in c:
            return '{} {} {} {} L={} W={} M={}'.format(
                name, n1, n2, c['primitive'], c['L'], c['W'], c['M']
            )
        return 'R_{} {} {} {}'.format(name, n1, n2, c['value'])

    def _replace_node(self, logical_line, node_position, new_node):
        tokens = logical_line.split()
        token_index = 1 + node_position
        if token_index >= len(tokens):
            raise FaultInjectionError('Position de noeud invalide')
        tokens[token_index] = new_node
        return ' '.join(tokens)

    def _apply_parametric(self, c, fault):
        """Modifie directement la valeur/le parametre du composant (pas
        d'element ajoute, contrairement a OPEN/SHORT) : c'est une deviation
        intrinseque du composant lui-meme."""
        param = fault.metadata.get('param')
        delta_pct = fault.metadata.get('delta_pct')

        if param is None or delta_pct is None:
            raise FaultInjectionError(
                'Faute parametrique mal formee pour {}'.format(c.name)
            )

        original_str = c.model if param == 'VALUE' else c.parameters.get(param)
        if original_str is None:
            raise FaultInjectionError(
                'Parametre {} introuvable sur {}'.format(param, c.name)
            )

        try:
            original_value = parse_spice_value(original_str)
        except SpiceValueError as exc:
            raise FaultInjectionError(str(exc))

        new_value = original_value * (1.0 + delta_pct / 100.0)
        new_str = format_spice_value(new_value)

        tokens = c.raw_text.split()
        replaced = False

        if param == 'VALUE':
            for i, tok in enumerate(tokens):
                if tok == original_str:
                    tokens[i] = new_str
                    replaced = True
                    break
        else:
            for i, tok in enumerate(tokens):
                if '=' in tok:
                    key, _ = tok.split('=', 1)
                    if key.upper() == param:
                        tokens[i] = '{}={}'.format(key, new_str)
                        replaced = True
                        break

        if not replaced:
            raise FaultInjectionError(
                'Impossible de localiser le parametre {} sur {}'.format(param, c.name)
            )

        return ' '.join(tokens), []

    def _find_component(self, circuit, fault):
        for c in circuit.all_components():
            if c.name == fault.component_name and c.subckt_name == fault.subckt_name:
                return c
        return None

    def _safe(self, text):
        return re.sub(r'[^A-Za-z0-9_]', '_', text)
