from fault_injection.checking.dynamic_checker import check_record


def evaluate_golden_results(results, specs):
    valid_by_corner = {}

    for result in results:
        if result.simulation_status != 'SUCCESS':
            valid_by_corner[result.corner] = False
            continue

        records = result.measurements.get('records', [])
        if not records:
            valid_by_corner[result.corner] = False
            continue

        valid = True
        for record in records:
            if not check_record(record, specs)['passed']:
                valid = False
                break

        valid_by_corner[result.corner] = valid

    return valid_by_corner
