from fault_injection.models.simulation_result import SimulationResult
from fault_injection.checking.dynamic_checker import classify_fault_simulation


def test_detection():
    specs = {'gain': {'name':'gain','min':0.9,'max':1.1}}
    result = SimulationResult('r1','f1','TT','SUCCESS', measurements={'records':[{'gain':0.8}]})
    classify_fault_simulation(result, specs, True)
    assert result.detection_status == 'DETECTED'
