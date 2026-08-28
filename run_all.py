#!/usr/bin/env python3
"""Lance la campagne pour TOUS les circuits enregistres dans config/circuits.json,
les uns apres les autres, puis affiche un resume comparatif.

Usage:
    ./run_all.py                 -> campagne COMPLETE sur chaque circuit (defaut)
    ./run_all.py smoke           -> smoke test (3 fautes, corner TT) sur chaque circuit
    ./run_all.py smoke-gen       -> generation seule sur chaque circuit (pas de Spectre)
    ./run_all.py medium          -> 10 fautes, 5 corners, sur chaque circuit
"""
import json
import os
import sys
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_circuits():
    path = os.path.join(SCRIPT_DIR, 'config', 'circuits.json')
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def main():
    circuits = load_circuits()
    mode_args = sys.argv[1:]

    if not circuits:
        print("Aucun circuit enregistre dans config/circuits.json.")
        sys.exit(1)

    summary = []

    for name in sorted(circuits.keys()):
        print('=' * 70)
        print('Circuit: {}'.format(name))
        print('=' * 70)

        start = time.time()
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, 'run_campaign.py'), name] + mode_args
        result = subprocess.run(cmd)
        elapsed = time.time() - start

        status = 'OK' if result.returncode == 0 else 'ECHEC (code {})'.format(result.returncode)

        coverage = None
        results_dir = circuits[name].get('results', 'results_{}'.format(name.lower()))
        coverage_path = os.path.join(SCRIPT_DIR, results_dir, 'coverage_summary.json')
        if os.path.exists(coverage_path):
            try:
                with open(coverage_path, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
                coverage = data.get('union', {}).get('coverage_percent')
            except Exception:
                coverage = None

        summary.append((name, status, elapsed, coverage))
        print()

    print('=' * 70)
    print('RESUME GLOBAL')
    print('=' * 70)
    header = '{:<15} {:<20} {:>12} {:>15}'.format(
        'Circuit', 'Statut', 'Duree (s)', 'Couverture'
    )
    print(header)
    print('-' * len(header))
    for name, status, elapsed, coverage in summary:
        cov_str = '{:.2f}%'.format(coverage) if coverage is not None else 'N/A'
        print('{:<15} {:<20} {:>12.1f} {:>15}'.format(name, status, elapsed, cov_str))


if __name__ == '__main__':
    main()
