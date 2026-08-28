from fault_injection.models.fault import Fault
from fault_injection.spice_utils import parse_spice_value, SpiceValueError


class FaultGenerator(object):
    def __init__(self, default_weight=1.0, parametric_enabled=False, parametric_pct=20.0):
        self.default_weight = float(default_weight)
        self.parametric_enabled = bool(parametric_enabled)
        # Accepte soit un seul pourcentage (20.0), soit une liste de plusieurs
        # pourcentages a tester ([20, 50]) pour couvrir plusieurs amplitudes
        # de deviation en une seule campagne.
        if isinstance(parametric_pct, (list, tuple)):
            self.parametric_pcts = [float(p) for p in parametric_pct]
        else:
            self.parametric_pcts = [float(parametric_pct)]

    def generate(self, circuit):
        faults = []
        for component in circuit.all_components():
            faults.extend(self._generate_for_component(component))
        return faults

    def _generate_for_component(self, c):
        faults = []
        if c.component_type == 'mosfet':
            faults.extend(self._mos_faults(c))
            if self.parametric_enabled:
                faults.extend(self._parametric_mos(c))
        elif c.component_type == 'bjt':
            faults.extend(self._bjt_faults(c))
            if self.parametric_enabled:
                faults.extend(self._parametric_bjt(c))
        elif c.component_type in ('resistor', 'capacitor', 'inductor', 'diode'):
            faults.extend(self._two_terminal_faults(c))
            if self.parametric_enabled and c.component_type != 'diode':
                faults.extend(self._parametric_two_terminal(c))
        return faults

    def _mos_faults(self, c):
        if len(c.nodes) < 4:
            return []

        n = {'D': c.nodes[0], 'G': c.nodes[1], 'S': c.nodes[2], 'B': c.nodes[3]}
        faults = []

        short_pairs = [
            ('D','S','DS_SHORT'), ('G','D','GD_SHORT'),
            ('G','S','GS_SHORT'), ('D','B','DB_SHORT'),
            ('S','B','SB_SHORT')
        ]

        for a, b, subtype in short_pairs:
            if n[a] == n[b]:
                continue
            faults.append(self._new_fault(c, 'SHORT', subtype, [a,b], [n[a],n[b]]))

        for terminal in ('D','S','B','G'):
            faults.append(self._new_fault(
                c, 'OPEN', '{}_OPEN'.format(terminal), [terminal], [n[terminal]]
            ))

        return faults

    def _bjt_faults(self, c):
        if len(c.nodes) < 3:
            return []

        n = {'C': c.nodes[0], 'B': c.nodes[1], 'E': c.nodes[2]}
        faults = []

        for a, b, subtype in (
            ('B','E','BE_SHORT'), ('B','C','BC_SHORT'), ('C','E','CE_SHORT')
        ):
            if n[a] == n[b]:
                continue
            faults.append(self._new_fault(c, 'SHORT', subtype, [a,b], [n[a],n[b]]))

        for terminal in ('B','C','E'):
            faults.append(self._new_fault(
                c, 'OPEN', '{}_OPEN'.format(terminal), [terminal], [n[terminal]]
            ))

        return faults

    def _two_terminal_faults(self, c):
        if len(c.nodes) < 2:
            return []

        n1, n2 = c.nodes[0], c.nodes[1]
        faults = []

        if n1 != n2:
            faults.append(self._new_fault(c, 'SHORT', 'SHORT', ['1','2'], [n1,n2]))

        faults.append(self._new_fault(
            c, 'OPEN', 'OPEN', ['1/2'], [n1,n2],
            metadata={'collapsed_count': 2, 'reason': 'two_terminal_open_equivalence'}
        ))

        return faults

    def _new_fault(self, c, fault_type, subtype, terminals, nodes, metadata=None):
        fault_id = '{}__{}__{}'.format(c.subckt_name or 'TOP', c.name, subtype)
        return Fault(
            fault_id=fault_id, fault_type=fault_type, subtype=subtype,
            component_name=c.name, terminals=terminals, nodes=nodes,
            weight=self.default_weight, subckt_name=c.subckt_name,
            metadata=metadata or {}
        )

    # ============================================================
    # Fautes parametriques (deviation de +/- X% d'un parametre)
    # ============================================================
    # Le pourcentage n'est pas impose par IEEE Std 2427 (qui specifie la
    # methode de comptage de couverture, pas la magnitude des fautes) : c'est
    # un choix de methodologie, configurable via parametric_pct, avec ±20%
    # comme valeur par defaut usuelle dans la litterature (typiquement
    # ±10% a ±50% selon les etudes).

    def _param_pair(self, c, param):
        faults = []
        for pct in self.parametric_pcts:
            plus = self._new_fault(
                c, 'PARAMETRIC', '{}_PLUS{:g}PCT'.format(param, pct),
                [param], list(c.nodes),
                metadata={'param': param, 'delta_pct': pct}
            )
            minus = self._new_fault(
                c, 'PARAMETRIC', '{}_MINUS{:g}PCT'.format(param, pct),
                [param], list(c.nodes),
                metadata={'param': param, 'delta_pct': -pct}
            )
            faults.extend([plus, minus])
        return faults

    def _parametric_mos(self, c):
        faults = []
        for param in ('L', 'W'):
            if param in c.parameters:
                faults.extend(self._param_pair(c, param))
        return faults

    def _parametric_bjt(self, c):
        faults = []
        if 'M' in c.parameters:
            faults.extend(self._param_pair(c, 'M'))
        return faults

    def _parametric_two_terminal(self, c):
        faults = []
        has_named = False

        # Cas 1 : primitive de fonderie avec parametres nommes L/W
        # (ex: primitive_rpoly2 L=815e-6 W=2e-6 M=1).
        for param in ('L', 'W'):
            if param in c.parameters:
                faults.extend(self._param_pair(c, param))
                has_named = True

        # Cas 2 : composant SPICE ideal avec valeur positionnelle simple
        # (ex: "R1 vin vout 1k"), stockee dans c.model par le parser.
        if not has_named and c.model is not None:
            try:
                parse_spice_value(c.model)
                faults.extend(self._param_pair(c, 'VALUE'))
            except SpiceValueError:
                pass

        return faults
