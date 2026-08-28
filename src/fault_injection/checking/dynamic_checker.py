def check_record(record, specs):
    failed = []
    details = {}

    for key, spec in specs.items():
        name = spec['name']

        if key not in record:
            failed.append(name)
            details[name] = {
                'present': False, 'passed': False, 'value': None,
                'min': spec['min'], 'max': spec['max']
            }
            continue

        value = record[key]
        passed = isinstance(value, (int, float))

        if passed and spec['min'] is not None and value < spec['min']:
            passed = False
        if passed and spec['max'] is not None and value > spec['max']:
            passed = False

        if not passed:
            failed.append(name)

        details[name] = {
            'present': True, 'passed': passed, 'value': value,
            'min': spec['min'], 'max': spec['max']
        }

    return {'passed': len(failed) == 0, 'failed_specs': failed, 'details': details}


def classify_fault_simulation(sim_result, specs, golden_valid):
    if sim_result.simulation_status != 'SUCCESS':
        sim_result.detection_status = 'UNKNOWN'
        return sim_result

    if not golden_valid:
        sim_result.detection_status = 'UNKNOWN'
        return sim_result

    records = sim_result.measurements.get('records', [])
    if not records:
        sim_result.detection_status = 'UNKNOWN'
        return sim_result

    failed = []
    for record in records:
        checked = check_record(record, specs)
        if not checked['passed']:
            for name in checked['failed_specs']:
                if name not in failed:
                    failed.append(name)

    sim_result.failed_specs = failed
    sim_result.detection_status = 'DETECTED' if failed else 'UNDETECTED'
    return sim_result
