#!/usr/bin/env python3
"""Lance une campagne d'injection de fautes pour un circuit enregistre dans
config/circuits.json, sans avoir a retaper tous les chemins a chaque fois.

Usage:
    ./run_campaign.py <NOM_CIRCUIT>                  -> campagne complete
    ./run_campaign.py <NOM_CIRCUIT> smoke             -> 3 fautes, corner TT, Spectre reel
    ./run_campaign.py <NOM_CIRCUIT> smoke-gen          -> idem, generation seule (pas de Spectre)
    ./run_campaign.py <NOM_CIRCUIT> medium             -> 10 fautes, 5 corners
    ./run_campaign.py <NOM_CIRCUIT> --limit-faults 20  -> options main.py passees telles quelles
    ./run_campaign.py                                  -> liste les circuits disponibles
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'src'))

SHORTCUTS = {
    'smoke': ['--limit-faults', '3', '--only-corner', 'TT'],
    'smoke-gen': ['--limit-faults', '3', '--only-corner', 'TT', '--generate-only'],
    'medium': ['--limit-faults', '10'],
    'full': [],
}


def load_circuits():
    path = os.path.join(SCRIPT_DIR, 'config', 'circuits.json')
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def resolve_path(value):
    """Les chemins de circuits.json sont relatifs a la racine du projet,
    sauf s'ils sont deja absolus."""
    if os.path.isabs(value):
        return value
    return os.path.join(SCRIPT_DIR, value)


def print_usage(circuits):
    print(__doc__)
    print("Circuits disponibles:", ', '.join(sorted(circuits.keys())))


def main():
    circuits = load_circuits()

    if len(sys.argv) < 2:
        print_usage(circuits)
        sys.exit(1)

    circuit_name = sys.argv[1]
    rest = sys.argv[2:]

    if circuit_name not in circuits:
        print("Circuit inconnu: {}".format(circuit_name))
        print("Circuits disponibles:", ', '.join(sorted(circuits.keys())))
        sys.exit(1)

    entry = circuits[circuit_name]

    if rest and rest[0] in SHORTCUTS:
        extra_args = SHORTCUTS[rest[0]] + rest[1:]
    else:
        extra_args = rest

    results_dir = entry.get(
        'results', 'results_{}'.format(circuit_name.lower())
    )

    argv = [
        'main.py',
        '--netlist', resolve_path(entry['netlist']),
        '--testbench', resolve_path(entry['testbench']),
        '--specs', resolve_path(entry['specs']),
        '--config', resolve_path(entry.get('config', 'config/framework.json')),
        '--process-dir', resolve_path(entry.get('process_dir', 'process_models')),
        '--results', resolve_path(results_dir),
    ] + extra_args

    print('>>> Circuit: {}'.format(circuit_name))
    print('>>> {}'.format(' '.join(argv[1:])))
    print()

    sys.argv = argv

    from fault_injection.main import main as run_main
    run_main()


if __name__ == '__main__':
    main()
