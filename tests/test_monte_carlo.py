import os
import random

from fault_injection.models.circuit import Circuit, SubCircuit
from fault_injection.models.component import Component
from fault_injection.monte_carlo.injector import MonteCarloInjector


def _make_circuit():
    circuit = Circuit()
    sub = SubCircuit(name='TESTSUB', ports=['a', 'b'])

    r1 = Component(
        name='R1', component_type='resistor', nodes=['a', 'b'],
        model='1k', parameters={},
        raw_text='R1 a b 1k', start_line=2, end_line=2, subckt_name='TESTSUB'
    )
    m1 = Component(
        name='m1', component_type='mosfet', nodes=['a', 'b', 'a', 'b'],
        model='nmos1', parameters={'L': '1e-6', 'W': '2e-6'},
        raw_text='m1 a b a b nmos1 L=1e-6 W=2e-6', start_line=3, end_line=3,
        subckt_name='TESTSUB'
    )
    sub.add_component(r1)
    sub.add_component(m1)
    circuit.add_subcircuit(sub)
    return circuit


def test_monte_carlo_perturbs_all_components_simultaneously(tmpdir):
    circuit = _make_circuit()
    source = str(tmpdir.join('src.sub'))
    with open(source, 'w') as handle:
        handle.write('.subckt TESTSUB a b\nR1 a b 1k\nm1 a b a b nmos1 L=1e-6 W=2e-6\n.ends\n')

    injector = MonteCarloInjector(sigma_pct=10.0, rng=random.Random(0))
    output = str(tmpdir.join('trial.sub'))
    applied = injector.generate_trial(source, circuit, output)

    # R1 (VALUE) + m1 (L et W) = 3 perturbations en un seul essai.
    assert len(applied) == 3
    params_touched = set((a['component'], a['param']) for a in applied)
    assert ('R1', 'VALUE') in params_touched
    assert ('m1', 'L') in params_touched
    assert ('m1', 'W') in params_touched

    with open(output) as handle:
        content = handle.read()
    # Les valeurs nominales exactes (1k, 1e-6, 2e-6) ne doivent plus apparaitre
    # telles quelles : chacune a ete perturbee.
    assert 'R1 a b 1k' not in content
    assert 'L=1e-6' not in content


def test_monte_carlo_reproducible_with_seed():
    circuit = _make_circuit()
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        source = os.path.join(d, 'src.sub')
        with open(source, 'w') as handle:
            handle.write('.subckt TESTSUB a b\nR1 a b 1k\nm1 a b a b nmos1 L=1e-6 W=2e-6\n.ends\n')

        out1 = os.path.join(d, 'trial1.sub')
        out2 = os.path.join(d, 'trial2.sub')

        MonteCarloInjector(sigma_pct=10.0, rng=random.Random(42)).generate_trial(source, circuit, out1)
        MonteCarloInjector(sigma_pct=10.0, rng=random.Random(42)).generate_trial(source, circuit, out2)

        with open(out1) as f1, open(out2) as f2:
            assert f1.read() == f2.read()
