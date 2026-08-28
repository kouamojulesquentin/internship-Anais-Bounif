from fault_injection.models.fault import Fault
from fault_injection.models.simulation_result import SimulationResult
from fault_injection.metrics.ieee2427 import calculate_coverage


def test_union_counts_fault_once():
    faults = [
        Fault('f1','OPEN','OPEN','r1',['1'],['a'],1.0),
        Fault('f2','SHORT','SHORT','r2',['1','2'],['a','b'],1.0)
    ]
    results = []
    for corner in ['TT','FF']:
        r1 = SimulationResult('r1'+corner,'f1',corner,'SUCCESS')
        r1.detection_status = 'DETECTED' if corner == 'FF' else 'UNDETECTED'
        results.append(r1)
        r2 = SimulationResult('r2'+corner,'f2',corner,'SUCCESS')
        r2.detection_status = 'UNDETECTED'
        results.append(r2)
    coverage = calculate_coverage(faults, results, ['TT','FF'])
    assert coverage['union']['coverage'] == 0.5
