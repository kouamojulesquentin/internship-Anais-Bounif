import csv
import json
import os
import sqlite3


def _ensure(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


def write_fault_universe(path, faults):
    _ensure(os.path.dirname(path))
    fields = ['fault_id','fault_type','subtype','component_name','terminals','nodes','weight','subckt_name','metadata']
    with open(path, 'w', encoding='utf-8', errors='replace') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for fault in faults:
            writer.writerow(fault.to_dict())


def write_results_csv(path, results):
    _ensure(os.path.dirname(path))
    fields = ['run_id','fault_id','corner','simulation_status','detection_status','failed_specs','mt0_path','log_path','sim_time_s','error_message']
    with open(path, 'w', encoding='utf-8', errors='replace') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_dict())


def write_spec_values_csv(path, results, specs):
    """CSV detaille: une ligne par simulation, avec la valeur mesuree de
    CHAQUE spec (colonnes <spec>_value / <spec>_passed), en plus du statut
    global. C'est le fichier a regarder pour comprendre POURQUOI une faute
    est detectee (quelle spec casse, de combien)."""
    _ensure(os.path.dirname(path))

    spec_names = [spec['name'] for spec in specs.values()]

    fields = ['run_id', 'fault_id', 'corner', 'simulation_status', 'detection_status']
    for name in spec_names:
        fields.append('{}_value'.format(name))
        fields.append('{}_passed'.format(name))
    fields.append('failed_specs')

    with open(path, 'w', encoding='utf-8', errors='replace') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for result in results:
            row = {
                'run_id': result.run_id,
                'fault_id': result.fault_id,
                'corner': result.corner,
                'simulation_status': result.simulation_status,
                'detection_status': result.detection_status,
                'failed_specs': ','.join(result.failed_specs),
            }

            records = result.measurements.get('records', [])
            record = records[0] if records else {}

            for key, spec in specs.items():
                name = spec['name']
                value = record.get(key)
                row['{}_value'.format(name)] = value if value is not None else ''

                if value is None or not isinstance(value, (int, float)):
                    row['{}_passed'.format(name)] = ''
                    continue

                passed = True
                if spec['min'] is not None and value < spec['min']:
                    passed = False
                if spec['max'] is not None and value > spec['max']:
                    passed = False
                row['{}_passed'.format(name)] = str(passed)

            writer.writerow(row)


def write_measurements_csv(path, results):
    """CSV brut: une ligne par simulation avec TOUTES les mesures trouvees
    dans les fichiers .mt0/.mt1/... (sondes internes, mesures AC, etc.),
    pas seulement celles verifiees contre specs.json. Colonnes dynamiques
    = union de toutes les cles de mesure rencontrees."""
    _ensure(os.path.dirname(path))

    all_keys = []
    seen_keys = set()
    rows = []

    for result in results:
        records = result.measurements.get('records', [])
        record = records[0] if records else {}

        for key in record.keys():
            if key not in seen_keys:
                seen_keys.add(key)
                all_keys.append(key)

        rows.append((result, record))

    fields = ['run_id', 'fault_id', 'corner', 'simulation_status'] + all_keys

    with open(path, 'w', encoding='utf-8', errors='replace') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for result, record in rows:
            row = {
                'run_id': result.run_id,
                'fault_id': result.fault_id,
                'corner': result.corner,
                'simulation_status': result.simulation_status,
            }
            for key in all_keys:
                row[key] = record.get(key, '')
            writer.writerow(row)


def write_coverage_json(path, coverage):
    _ensure(os.path.dirname(path))
    with open(path, 'w', encoding='utf-8', errors='replace') as handle:
        json.dump(coverage, handle, indent=2, sort_keys=True)


def write_test_escape_csv(path, coverage):
    """CSV dedie a la terminologie test IC standard : test_escape_percent
    (fautes non detectees, i.e. defauts qui 'echappent' au test) plutot que
    detection_percent. Une ligne par corner + une ligne 'union' (tous
    corners combines). Reutilise les poids deja calcules par
    calculate_coverage() (memes denominateurs que coverage_percent, donc
    test_escape_percent + coverage_percent + unknown_percent = 100% pour
    chaque scope)."""
    _ensure(os.path.dirname(path))

    fields = [
        'scope', 'total_weight', 'detected_weight', 'test_escape_weight',
        'unknown_weight', 'coverage_percent', 'test_escape_percent',
        'unknown_percent'
    ]

    def _row(scope, entry):
        total = entry['total_weight']
        detected = entry['detected_weight']
        escaped = entry['undetected_weight']
        unknown = entry['unknown_weight']

        def _pct(weight):
            return round(100.0 * weight / total, 4) if total else ''

        return {
            'scope': scope,
            'total_weight': total,
            'detected_weight': detected,
            'test_escape_weight': escaped,
            'unknown_weight': unknown,
            'coverage_percent': _pct(detected),
            'test_escape_percent': _pct(escaped),
            'unknown_percent': _pct(unknown),
        }

    with open(path, 'w', newline='', encoding='utf-8', errors='replace') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for corner, entry in sorted(coverage['per_corner'].items()):
            writer.writerow(_row(corner, entry))

        writer.writerow(_row('union', coverage['union']))


def write_results_sqlite(path, results):
    _ensure(os.path.dirname(path))
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute('DROP TABLE IF EXISTS results')
    cur.execute('''CREATE TABLE results (
        run_id TEXT, fault_id TEXT, corner TEXT, simulation_status TEXT,
        detection_status TEXT, failed_specs TEXT, mt0_path TEXT,
        log_path TEXT, sim_time_s REAL, error_message TEXT
    )''')

    for result in results:
        row = result.to_dict()
        cur.execute('INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?)', (
            row['run_id'], row['fault_id'], row['corner'], row['simulation_status'],
            row['detection_status'], row['failed_specs'], row['mt0_path'],
            row['log_path'], row['sim_time_s'], row['error_message']
        ))

    con.commit()
    con.close()
