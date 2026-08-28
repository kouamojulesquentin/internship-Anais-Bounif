import os
import re


class MT0ParseError(Exception):
    pass


def find_mt0(testbench_path):
    base, _ = os.path.splitext(testbench_path)

    direct = base + '.mt0'
    if os.path.exists(direct):
        return direct

    nested = os.path.join(base + '.raw', 'spectre.mt0')
    if os.path.exists(nested):
        return nested

    folder = os.path.dirname(testbench_path) or '.'
    for filename in sorted(os.listdir(folder)):
        if filename.lower().endswith('.mt0'):
            return os.path.join(folder, filename)

    return None


def find_all_mt_files(testbench_path):
    """Spectre ecrit une sortie de mesures separee par type d analyse:
    .mt0 pour la premiere analyse (souvent TRAN), .mt1 pour la seconde
    (souvent AC), etc. On les recupere tous pour ne perdre aucune mesure
    (ex: PSRR_dB_1k qui n existe que dans .mt1)."""
    base, _ = os.path.splitext(testbench_path)
    folder = os.path.dirname(testbench_path) or '.'
    base_name = os.path.basename(base)

    found = {}

    pattern = re.compile(re.escape(base_name) + r'\.mt(\d+)$', re.IGNORECASE)
    if os.path.isdir(folder):
        for filename in os.listdir(folder):
            match = pattern.match(filename)
            if match:
                found[int(match.group(1))] = os.path.join(folder, filename)

    nested_dir = base + '.raw'
    if os.path.isdir(nested_dir):
        nested_pattern = re.compile(r'.*\.mt(\d+)$', re.IGNORECASE)
        for filename in os.listdir(nested_dir):
            match = nested_pattern.match(filename)
            if match:
                found.setdefault(int(match.group(1)), os.path.join(nested_dir, filename))

    return [found[k] for k in sorted(found.keys())]


def parse_mt0(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        raw_lines = handle.readlines()

    useful = []
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith('$') or line.lower().startswith('.title'):
            continue
        useful.append(line)

    if not useful:
        raise MT0ParseError('Fichier mt0 vide.')

    headers = []
    data_start = None

    for index, line in enumerate(useful):
        tokens = line.split()
        headers.extend(tokens)
        if any(token.lower() == 'alter#' for token in tokens):
            data_start = index + 1
            break

    if data_start is None:
        raise MT0ParseError('Colonne alter# introuvable.')

    values = []
    for line in useful[data_start:]:
        values.extend(line.split())

    width = len(headers)
    if len(values) < width:
        raise MT0ParseError('Pas assez de valeurs.')

    records = []
    for start in range(0, len(values), width):
        chunk = values[start:start + width]
        if len(chunk) != width:
            break

        record = {}
        for name, value in zip(headers, chunk):
            key = name.lower()
            try:
                record[key] = float(value)
            except ValueError:
                record[key] = value
        records.append(record)

    if not records:
        raise MT0ParseError('Aucun record valide.')

    return records


def parse_all_records(testbench_path):
    """Fusionne .mt0, .mt1, .mt2... en un seul enregistrement de mesures.
    Chaque fichier correspond a un type d analyse (TRAN, AC, ...) pour LE
    MEME run: leurs alter# respectifs ne se correspondent pas entre fichiers
    (observe en pratique: .mt0 alter#=1 pour TRAN, .mt1 alter#=2 pour AC),
    donc on fusionne toutes les mesures de tous les fichiers dans un seul
    dictionnaire plutot que d aligner par alter#."""
    paths = find_all_mt_files(testbench_path)
    if not paths:
        return []

    merged = {}
    for path in paths:
        records = parse_mt0(path)
        for record in records:
            merged.update(record)

    return [merged] if merged else []
