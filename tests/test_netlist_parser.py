from fault_injection.netlist.parser import NetlistParser


def test_parentheses_and_continuation():
    text = '''
.subckt TEST in out vdd vss
m1 (out in vss vss) nmos1
+ L=1e-6
+ W=10e-6
xr1 in out primitive_rpoly2 L=2e-6 W=1e-6 M=1
.ends
'''
    circuit = NetlistParser().parse_text(text)
    comps = circuit.subcircuits['TEST'].components
    assert comps[0].nodes == ['out','in','vss','vss']
    assert comps[0].parameters['L'] == '1e-6'
    assert comps[0].start_line < comps[0].end_line
    assert comps[1].component_type == 'resistor'
