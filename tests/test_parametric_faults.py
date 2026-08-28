from fault_injection.models.circuit import Circuit
from fault_injection.models.component import Component
from fault_injection.faults.generator import FaultGenerator
from fault_injection.faults.injector import NetlistInjector


def _make_circuit():
    circuit = Circuit()
    circuit.add_subcircuit_name = None  # not used directly

    from fault_injection.models.circuit import SubCircuit
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


def test_parametric_disabled_by_default_no_change():
    circuit = _make_circuit()
    faults_default = FaultGenerator().generate(circuit)
    assert all(f.fault_type != 'PARAMETRIC' for f in faults_default)


def test_parametric_generates_plus_minus_pair():
    circuit = _make_circuit()
    faults = FaultGenerator(parametric_enabled=True, parametric_pct=20.0).generate(circuit)
    param_faults = [f for f in faults if f.fault_type == 'PARAMETRIC']

    ids = set(f.fault_id for f in param_faults)
    assert 'TESTSUB__R1__VALUE_PLUS20PCT' in ids
    assert 'TESTSUB__R1__VALUE_MINUS20PCT' in ids
    assert 'TESTSUB__m1__L_PLUS20PCT' in ids
    assert 'TESTSUB__m1__W_MINUS20PCT' in ids


def test_parametric_accepts_list_of_percentages():
    circuit = _make_circuit()
    faults = FaultGenerator(parametric_enabled=True, parametric_pct=[20, 50]).generate(circuit)
    param_faults = [f for f in faults if f.fault_type == 'PARAMETRIC']
    ids = set(f.fault_id for f in param_faults)

    assert 'TESTSUB__R1__VALUE_PLUS20PCT' in ids
    assert 'TESTSUB__R1__VALUE_MINUS20PCT' in ids
    assert 'TESTSUB__R1__VALUE_PLUS50PCT' in ids
    assert 'TESTSUB__R1__VALUE_MINUS50PCT' in ids
    # Un seul pourcentage donnait 8 fautes parametriques (R1: 2, m1: 4 -> total 6 en fait)
    # Deux pourcentages doivent exactement doubler le nombre de fautes parametriques.
    single = FaultGenerator(parametric_enabled=True, parametric_pct=20.0).generate(circuit)
    single_count = len([f for f in single if f.fault_type == 'PARAMETRIC'])
    assert len(param_faults) == single_count * 2


def test_parametric_injection_computes_correct_value():
    circuit = _make_circuit()
    faults = FaultGenerator(parametric_enabled=True, parametric_pct=20.0).generate(circuit)

    injector = NetlistInjector({
        'short_model': {'value': '1m'},
        'open_model': {'value': '1T'},
    })

    r1_plus = next(f for f in faults if f.fault_id == 'TESTSUB__R1__VALUE_PLUS20PCT')
    new_line, extra = injector._build_injection(
        next(c for c in circuit.all_components() if c.name == 'R1'), r1_plus
    )
    assert '1200.0' in new_line
    assert extra == []

    m1_minus = next(f for f in faults if f.fault_id == 'TESTSUB__m1__W_MINUS20PCT')
    new_line, extra = injector._build_injection(
        next(c for c in circuit.all_components() if c.name == 'm1'), m1_minus
    )
    assert 'W=1.6e-06' in new_line
