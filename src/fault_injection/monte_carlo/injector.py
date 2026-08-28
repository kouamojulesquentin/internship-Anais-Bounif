import os
import random

from fault_injection.spice_utils import parse_spice_value, format_spice_value, SpiceValueError


class MonteCarloInjector(object):
    """Genere UNE netlist d'essai Monte Carlo : contrairement a
    NetlistInjector (une faute a la fois), ici TOUS les composants
    eligibles (valeur R/C/L, L/W de primitive fonderie, L/W de MOSFET,
    M de BJT) sont perturbes SIMULTANEMENT, chacun par un tirage gaussien
    independant centre sur 0% (valeur nominale), d'ecart-type sigma_pct.

    Un ecart-type (sigma) plutot qu'une borne dure : c'est la convention
    standard en analyse de variation de process (correspond a la tolerance
    de fabrication 1-sigma d'un composant).
    """

    def __init__(self, sigma_pct, rng=None):
        self.sigma_pct = float(sigma_pct)
        self.rng = rng or random.Random()

    def _draw_deviation_pct(self):
        return self.rng.gauss(0.0, self.sigma_pct)

    def _eligible_params(self, component):
        params = []

        if component.component_type == 'mosfet':
            for p in ('L', 'W'):
                if p in component.parameters:
                    params.append(p)

        elif component.component_type == 'bjt':
            if 'M' in component.parameters:
                params.append('M')

        elif component.component_type in ('resistor', 'capacitor', 'inductor'):
            has_named = False
            for p in ('L', 'W'):
                if p in component.parameters:
                    params.append(p)
                    has_named = True
            if not has_named and component.model is not None:
                try:
                    parse_spice_value(component.model)
                    params.append('VALUE')
                except SpiceValueError:
                    pass

        return params

    def generate_trial(self, source_path, circuit, output_path):
        """Ecrit une netlist perturbee complete. Retourne la liste des
        deviations appliquees (component, param, deviation_pct) pour
        tracabilite/debug."""
        with open(source_path, 'r', encoding='utf-8', errors='replace') as handle:
            lines = handle.readlines()

        applied = []

        # Traiter du plus grand start_line au plus petit : un composant
        # multi-lignes (continuation '+') collapse en une seule ligne peut
        # decaler les indices des lignes SUIVANTES dans le fichier ; en
        # traitant a l'envers, seules les plages pas encore visitees sont
        # affectees par ce decalage.
        components = sorted(
            circuit.all_components(), key=lambda c: c.start_line, reverse=True
        )

        for component in components:
            params = self._eligible_params(component)
            if not params:
                continue

            tokens = component.raw_text.split()

            for param in params:
                original_str = (
                    component.model if param == 'VALUE'
                    else component.parameters.get(param)
                )
                if original_str is None:
                    continue

                try:
                    nominal = parse_spice_value(original_str)
                except SpiceValueError:
                    continue

                deviation_pct = self._draw_deviation_pct()
                new_value = nominal * (1.0 + deviation_pct / 100.0)
                new_str = format_spice_value(new_value)

                if param == 'VALUE':
                    for i, tok in enumerate(tokens):
                        if tok == original_str:
                            tokens[i] = new_str
                            break
                else:
                    for i, tok in enumerate(tokens):
                        if '=' in tok:
                            key, _ = tok.split('=', 1)
                            if key.upper() == param:
                                tokens[i] = '{}={}'.format(key, new_str)
                                break

                applied.append({
                    'component': component.name,
                    'param': param,
                    'deviation_pct': deviation_pct
                })

            new_line = ' '.join(tokens)
            start = component.start_line - 1
            end = component.end_line
            lines[start:end] = [new_line + '\n']

        folder = os.path.dirname(output_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        with open(output_path, 'w', encoding='utf-8', errors='replace') as handle:
            handle.writelines(lines)

        return applied
