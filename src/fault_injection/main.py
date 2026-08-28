from __future__ import print_function

import argparse
import json
import os
import shutil

from fault_injection.netlist.parser import NetlistParser
from fault_injection.specs.loader import load_specs
from fault_injection.faults.generator import FaultGenerator
from fault_injection.faults.collapsing import FaultCollapser
from fault_injection.faults.injector import NetlistInjector
from fault_injection.simulation.testbench_generator import TestbenchGenerator
from fault_injection.simulation.spectre_runner import SpectreRunner
from fault_injection.checking.golden_checker import evaluate_golden_results
from fault_injection.checking.dynamic_checker import classify_fault_simulation
from fault_injection.metrics.ieee2427 import calculate_coverage
from fault_injection.reporting.result_writer import (
    write_fault_universe, write_results_csv,
    write_coverage_json, write_results_sqlite,
    write_spec_values_csv, write_measurements_csv,
    write_test_escape_csv
)

GOLDEN_FAULT_ID = '__GOLDEN__'


def load_json(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        return json.load(handle)


def safe_name(text):
    return ''.join(ch if ch.isalnum() or ch in ('_','-') else '_' for ch in text)


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def build_golden_jobs(netlist_path, testbench_path, config, process_dir, results_dir):
    generator = TestbenchGenerator()
    jobs = []
    root = os.path.join(results_dir, 'golden')
    ensure_dir(root)

    for corner in config['corners']:
        corner_dir = os.path.join(root, corner)
        ensure_dir(corner_dir)

        local_netlist = os.path.join(corner_dir, 'golden.sub')
        shutil.copyfile(netlist_path, local_netlist)

        process_path = os.path.abspath(os.path.join(
            process_dir, config['process_files'][corner]
        ))

        local_tb = os.path.join(corner_dir, 'golden.circuit')
        generator.generate(
            testbench_path, local_tb, 'golden.sub', process_path,
            original_netlist_filename=os.path.basename(netlist_path)
        )

        jobs.append({
            'run_id': 'GOLDEN__{}'.format(corner),
            'fault_id': GOLDEN_FAULT_ID,
            'corner': corner,
            'workdir': corner_dir,
            'testbench': local_tb
        })

    return jobs


def build_fault_jobs(netlist_path, testbench_path, circuit, faults,
                     config, process_dir, results_dir):
    injector = NetlistInjector(config)
    generator = TestbenchGenerator()
    jobs = []
    root = os.path.join(results_dir, 'generated')
    ensure_dir(root)

    for fault in faults:
        fault_dir = os.path.join(root, safe_name(fault.fault_id))
        ensure_dir(fault_dir)

        base_faulty = os.path.join(fault_dir, 'netlist_faulted.sub')
        injector.inject_file(netlist_path, circuit, fault, base_faulty)

        for corner in config['corners']:
            corner_dir = os.path.join(fault_dir, corner)
            ensure_dir(corner_dir)

            local_netlist = os.path.join(corner_dir, 'netlist_faulted.sub')
            shutil.copyfile(base_faulty, local_netlist)

            process_path = os.path.abspath(os.path.join(
                process_dir, config['process_files'][corner]
            ))

            local_tb = os.path.join(corner_dir, 'testbench.circuit')
            generator.generate(
                testbench_path, local_tb, 'netlist_faulted.sub', process_path,
                original_netlist_filename=os.path.basename(netlist_path)
            )

            jobs.append({
                'run_id': '{}__{}'.format(fault.fault_id, corner),
                'fault_id': fault.fault_id,
                'corner': corner,
                'workdir': corner_dir,
                'testbench': local_tb
            })

    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--netlist', required=True)
    parser.add_argument('--testbench', required=True)
    parser.add_argument('--specs', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--process-dir', required=True)
    parser.add_argument('--results', default='results')
    parser.add_argument('--generate-only', action='store_true')
    parser.add_argument(
        '--limit-faults', type=int, default=None,
        help='Ne traiter que les N premieres fautes (smoke test avant campagne complete).'
    )
    parser.add_argument(
        '--only-corner', default=None,
        help='Ne simuler qu un seul corner (ex: TT) au lieu des 5, pour un test rapide.'
    )
    args = parser.parse_args()

    config = load_json(args.config)
    specs = load_specs(args.specs)
    ensure_dir(args.results)

    if args.only_corner:
        if args.only_corner not in config['corners']:
            raise ValueError('Corner inconnu: {}'.format(args.only_corner))
        config = dict(config)
        config['corners'] = [args.only_corner]

    # 1. Parser
    circuit = NetlistParser().parse_file(args.netlist)

    # 2. Univers de défauts
    faults = FaultGenerator(
        default_weight=config.get('fault_weight', 1.0),
        parametric_enabled=config.get('enable_parametric_faults', False),
        parametric_pct=config.get('parametric_deviation_pct', 20.0)
    ).generate(circuit)

    # 3. Collapsing
    faults = FaultCollapser().collapse(faults)

    if args.limit_faults is not None:
        faults = faults[:args.limit_faults]
        print('Mode smoke test: limite a {} fautes.'.format(len(faults)))

    write_fault_universe(
        os.path.join(args.results, 'defect_universe.csv'), faults
    )

    # 4. Golden jobs
    golden_jobs = build_golden_jobs(
        args.netlist, args.testbench, config,
        args.process_dir, args.results
    )

    # 5. Fault jobs = 1 faute x 5 corners
    fault_jobs = build_fault_jobs(
        args.netlist, args.testbench, circuit, faults,
        config, args.process_dir, args.results
    )

    print('Sous-circuits :', len(circuit.subcircuits))
    print('Composants    :', len(circuit.all_components()))
    print('Defauts       :', len(faults))
    print('Golden jobs   :', len(golden_jobs))
    print('Fault jobs    :', len(fault_jobs))

    if args.generate_only:
        print('Generation terminee; Spectre non lance.')
        return

    runner = SpectreRunner(
        spectre_command=config.get('spectre_command', 'spectre'),
        workers=config.get('workers', 10),
        timeout_seconds=config.get('timeout_seconds', 600)
    )

    # 6. Golden simulation
    golden_results = runner.run_jobs(golden_jobs)
    golden_valid = evaluate_golden_results(golden_results, specs)
    print('Golden validity:', golden_valid)

    # 7. Simulations fautées
    fault_results = runner.run_jobs(fault_jobs)

    # 8. Classification DETECTED / UNDETECTED / UNKNOWN
    checked_results = []
    for result in fault_results:
        checked_results.append(
            classify_fault_simulation(
                result,
                specs,
                golden_valid.get(result.corner, False)
            )
        )

    # 9. Reporting
    write_results_csv(
        os.path.join(args.results, 'simulation_results.csv'),
        checked_results
    )
    write_results_sqlite(
        os.path.join(args.results, 'simulation_results.db'),
        checked_results
    )

    # CSV detailles (golden + fautes) avec valeurs mesurees explicites,
    # utiles pour comprendre pourquoi une faute est detectee.
    all_results = list(golden_results) + list(checked_results)
    write_spec_values_csv(
        os.path.join(args.results, 'spec_values.csv'),
        all_results, specs
    )
    write_measurements_csv(
        os.path.join(args.results, 'measurements_full.csv'),
        all_results
    )

    # 10. Couverture
    coverage = calculate_coverage(
        faults, checked_results, config['corners']
    )
    coverage['golden_valid'] = golden_valid

    write_coverage_json(
        os.path.join(args.results, 'coverage_summary.json'),
        coverage
    )

    write_test_escape_csv(
        os.path.join(args.results, 'test_escape_summary.csv'),
        coverage
    )

    print('Coverage union = {:.2f}%'.format(
        coverage['union']['coverage_percent']
    ))
    print('Test escape union = {:.2f}%'.format(
        100.0 * coverage['union']['undetected_weight'] / coverage['union']['total_weight']
        if coverage['union']['total_weight'] else 0.0
    ))


if __name__ == '__main__':
    main()
