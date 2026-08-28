def calculate_coverage(faults, results, corners):
    result_map = {(r.fault_id, r.corner): r for r in results}
    total_weight = sum(f.weight for f in faults)

    per_corner = {}
    for corner in corners:
        detected = 0.0
        undetected = 0.0
        unknown = 0.0

        for fault in faults:
            result = result_map.get((fault.fault_id, corner))

            if result is None or result.detection_status == 'UNKNOWN':
                unknown += fault.weight
            elif result.detection_status == 'DETECTED':
                detected += fault.weight
            else:
                undetected += fault.weight

        coverage = detected / total_weight if total_weight else 0.0
        per_corner[corner] = {
            'detected_weight': detected,
            'undetected_weight': undetected,
            'unknown_weight': unknown,
            'total_weight': total_weight,
            'coverage': coverage,
            'coverage_percent': coverage * 100.0
        }

    union_detected = 0.0
    union_undetected = 0.0
    union_unknown = 0.0

    for fault in faults:
        states = []
        for corner in corners:
            result = result_map.get((fault.fault_id, corner))
            states.append('UNKNOWN' if result is None else result.detection_status)

        if 'DETECTED' in states:
            union_detected += fault.weight
        elif all(state == 'UNKNOWN' for state in states):
            union_unknown += fault.weight
        else:
            union_undetected += fault.weight

    union_coverage = union_detected / total_weight if total_weight else 0.0

    by_type = {}
    fault_types_present = sorted(set(f.fault_type for f in faults))
    for fault_type in fault_types_present:
        subset = [f for f in faults if f.fault_type == fault_type]
        subset_total = sum(f.weight for f in subset)
        subset_detected = 0.0

        for fault in subset:
            if any(
                result_map.get((fault.fault_id, corner)) is not None and
                result_map[(fault.fault_id, corner)].detection_status == 'DETECTED'
                for corner in corners
            ):
                subset_detected += fault.weight

        coverage = subset_detected / subset_total if subset_total else 0.0
        by_type[fault_type] = {
            'detected_weight': subset_detected,
            'total_weight': subset_total,
            'coverage': coverage,
            'coverage_percent': coverage * 100.0
        }

    return {
        'per_corner': per_corner,
        'union': {
            'detected_weight': union_detected,
            'undetected_weight': union_undetected,
            'unknown_weight': union_unknown,
            'total_weight': total_weight,
            'coverage': union_coverage,
            'coverage_percent': union_coverage * 100.0
        },
        'by_type': by_type
    }
