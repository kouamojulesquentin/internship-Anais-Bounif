import argparse
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from fault_injection.netlist.parser import NetlistParser
from fault_injection.monte_carlo.injector import MonteCarloInjector
from fault_injection.simulation.testbench_generator import TestbenchGenerator
from fault_injection.simulation.spectre_runner import SpectreRunner
from fault_injection.specs.loader import load_specs


def load_json(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def ensure_dir(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


def check_trial(record, specs):
    """Verifie un essai contre les specs. Retourne (passed, failed_specs)."""
    failed = []
    for key, spec in specs.items():
        value = record.get(key)
        if value is None or not isinstance(value, (int, float)):
            failed.append(spec['name'])
            continue
        if spec['min'] is not None and value < spec['min']:
            failed.append(spec['name'])
        elif spec['max'] is not None and value > spec['max']:
            failed.append(spec['name'])
    return (len(failed) == 0, failed)


def main():
    parser = argparse.ArgumentParser(
        description='Analyse Monte Carlo de rendement (variation simultanee '
                    'de tous les composants, distribution gaussienne).'
    )
    parser.add_argument('--netlist', required=True)
    parser.add_argument('--testbench', required=True)
    parser.add_argument('--specs', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--process-dir', required=True)
    parser.add_argument('--results', default='results_monte_carlo')
    parser.add_argument('--num-trials', type=int, default=100)
    parser.add_argument('--sigma-pct', type=float, default=10.0,
                         help='Ecart-type (1-sigma) de la deviation gaussienne, en %%.')
    parser.add_argument('--corner', default='TT')
    parser.add_argument('--seed', type=int, default=None,
                         help='Graine aleatoire, pour des resultats reproductibles.')
    args = parser.parse_args()

    config = load_json(args.config)
    specs = load_specs(args.specs)
    ensure_dir(args.results)

    if args.corner not in config['corners']:
        raise ValueError('Corner inconnu: {}'.format(args.corner))

    process_path = os.path.abspath(
        os.path.join(args.process_dir, config['process_files'][args.corner])
    )

    circuit = NetlistParser().parse_file(args.netlist)

    rng = random.Random(args.seed)
    injector = MonteCarloInjector(sigma_pct=args.sigma_pct, rng=rng)
    tb_generator = TestbenchGenerator()

    trials_dir = os.path.join(args.results, 'trials')
    ensure_dir(trials_dir)

    jobs = []
    deviations_by_trial = {}

    print('Generation de {} essais (sigma={}%, corner={})...'.format(
        args.num_trials, args.sigma_pct, args.corner
    ))

    for i in range(args.num_trials):
        trial_id = 'trial_{:05d}'.format(i)
        workdir = os.path.join(trials_dir, trial_id)
        ensure_dir(workdir)

        netlist_out = os.path.join(workdir, 'netlist_mc.sub')
        applied = injector.generate_trial(args.netlist, circuit, netlist_out)
        deviations_by_trial[trial_id] = applied

        tb_out = os.path.join(workdir, 'testbench.circuit')
        tb_generator.generate(
            args.testbench, tb_out, os.path.basename(netlist_out), process_path,
            original_netlist_filename=os.path.basename(args.netlist)
        )

        jobs.append({
            'run_id': trial_id, 'fault_id': trial_id, 'corner': args.corner,
            'workdir': workdir, 'testbench': tb_out
        })

    print('Simulation de {} essais...'.format(len(jobs)))
    runner = SpectreRunner(
        spectre_command=config.get('spectre_command', 'spectre'),
        workers=config.get('workers', 10),
        timeout_seconds=config.get('timeout_seconds', 600)
    )
    results = runner.run_jobs(jobs)

    rows = []
    pass_count = 0
    fail_count = 0
    error_count = 0
    fail_spec_counts = {}

    for result in results:
        record = {}
        if result.simulation_status == 'SUCCESS':
            recs = result.measurements.get('records', [])
            record = recs[0] if recs else {}

        if result.simulation_status != 'SUCCESS':
            status = 'ERROR'
            error_count += 1
            passed = None
            failed_specs = []
        else:
            passed, failed_specs = check_trial(record, specs)
            if passed:
                status = 'PASS'
                pass_count += 1
            else:
                status = 'FAIL'
                fail_count += 1
                for name in failed_specs:
                    fail_spec_counts[name] = fail_spec_counts.get(name, 0) + 1

        row = {
            'trial_id': result.run_id,
            'simulation_status': result.simulation_status,
            'mc_status': status,
            'failed_specs': ','.join(failed_specs),
        }
        row.update(record)
        rows.append(row)

    all_keys = ['trial_id', 'simulation_status', 'mc_status', 'failed_specs']
    seen = set(all_keys)
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                all_keys.append(key)

    results_csv = os.path.join(args.results, 'monte_carlo_results.csv')
    with open(results_csv, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=all_keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    deviations_json = os.path.join(args.results, 'deviations_by_trial.json')
    with open(deviations_json, 'w', encoding='utf-8') as handle:
        json.dump(deviations_by_trial, handle, indent=2)

    total_simulated = pass_count + fail_count
    yield_pct = (100.0 * pass_count / total_simulated) if total_simulated else None
    yield_loss_pct = (100.0 - yield_pct) if yield_pct is not None else None

    summary = {
        'num_trials': args.num_trials,
        'sigma_pct': args.sigma_pct,
        'corner': args.corner,
        'seed': args.seed,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'error_count': error_count,
        'yield_percent': yield_pct,
        'yield_loss_percent': yield_loss_pct,
        'fail_spec_counts': fail_spec_counts,
    }
    summary_json = os.path.join(args.results, 'monte_carlo_summary.json')
    with open(summary_json, 'w', encoding='utf-8') as handle:
        json.dump(summary, handle, indent=2)

    # CSV dedie aux metriques de synthese (comme les autres rapports du
    # framework), plus facile a ouvrir dans Excel/LibreOffice que le JSON.
    metrics_csv = os.path.join(args.results, 'monte_carlo_metrics.csv')
    with open(metrics_csv, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow([
            'corner', 'sigma_pct', 'num_trials', 'pass_count', 'fail_count',
            'error_count', 'yield_percent', 'yield_loss_percent'
        ])
        writer.writerow([
            args.corner, args.sigma_pct, args.num_trials, pass_count,
            fail_count, error_count,
            '' if yield_pct is None else round(yield_pct, 4),
            '' if yield_loss_pct is None else round(yield_loss_pct, 4)
        ])

    print()
    print('Essais       :', args.num_trials)
    print('SUCCESS sim. :', total_simulated, '/ ERROR:', error_count)
    print('PASS         :', pass_count)
    print('FAIL         :', fail_count)
    if yield_pct is not None:
        print('Rendement (yield)     : {:.2f}%'.format(yield_pct))
        print('Perte de rendement (yield loss) : {:.2f}%'.format(yield_loss_pct))
    if fail_spec_counts:
        print('Specs en cause (nb d essais en echec) :')
        for name, count in sorted(fail_spec_counts.items(), key=lambda x: -x[1]):
            print('  {}: {}'.format(name, count))


if __name__ == '__main__':
    main()
