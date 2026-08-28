from fault_injection.netlist.parser import NetlistParser
from fault_injection.faults.generator import FaultGenerator


def test_mos_faults():
    text = '''
.subckt TEST d g s b
m1 d g s b nmos1 L=1u W=10u
.ends
'''
    circuit = NetlistParser().parse_text(text)
    subtypes = set(f.subtype for f in FaultGenerator().generate(circuit))
    assert 'DS_SHORT' in subtypes
    assert 'GD_SHORT' in subtypes
    assert 'GS_SHORT' in subtypes
    assert 'D_OPEN' in subtypes
    assert 'G_OPEN' in subtypes
