import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from fault_injection.models.simulation_result import SimulationResult
from fault_injection.simulation.mt0_parser import find_mt0, parse_all_records


def _detect_status(returncode, text):
    low = text.lower()

    if 'time limit exceeded' in low or 'timeout' in low:
        return 'TIMEOUT'

    if 'did not converge' in low or 'convergence failed' in low or 'singular' in low:
        return 'NON_CONVERGENCE'

    for token in (
        'fatal error', 'cannot open', 'no such file', 'syntax error',
        'subcircuit not found', 'aborted'
    ):
        if token in low:
            return 'SIMULATION_ERROR'

    if returncode != 0:
        return 'SIMULATION_ERROR'

    return 'SUCCESS'


def _spectre_env():
    """Force une locale UTF-8 pour le sous-processus Spectre. Si l'environnement
    (ex: script d'init Cadence) a bascule LANG/LC_ALL vers une locale non-UTF-8
    (C/POSIX), Spectre corrompt les caracteres accentues dans les chemins de
    fichiers (.INCLUDE ...), ce qui fait echouer la lecture de la netlist meme
    si le chemin ecrit par Python est parfaitement correct."""
    env = dict(os.environ)
    env['LANG'] = 'C.UTF-8'
    env['LC_ALL'] = 'C.UTF-8'
    return env


def _run_one(job):
    start = time.time()
    workdir = job['workdir']
    testbench = job['testbench']
    log_path = os.path.join(workdir, 'spectre.log')

    try:
        completed = subprocess.run(
            [
                job['spectre_command'],
                os.path.basename(testbench),
                '-raw', os.path.splitext(os.path.basename(testbench))[0] + '.raw'
            ],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',
            env=_spectre_env(),
            timeout=job['timeout_seconds']
        )
    except subprocess.TimeoutExpired:
        return SimulationResult(
            job['run_id'], job['fault_id'], job['corner'], 'TIMEOUT',
            sim_time_s=time.time() - start, error_message='Timeout'
        )
    except Exception as exc:
        return SimulationResult(
            job['run_id'], job['fault_id'], job['corner'], 'SIMULATION_ERROR',
            sim_time_s=time.time() - start, error_message=str(exc)
        )

    text = (completed.stdout or '') + '\n' + (completed.stderr or '')
    try:
        with open(log_path, 'w', encoding='utf-8', errors='replace') as handle:
            handle.write(text)
    except Exception:
        pass

    status = _detect_status(completed.returncode, text)
    if status != 'SUCCESS':
        return SimulationResult(
            job['run_id'], job['fault_id'], job['corner'], status,
            log_path=log_path, sim_time_s=time.time() - start,
            error_message=text[-4000:]
        )

    mt0_path = find_mt0(testbench)
    if mt0_path is None:
        return SimulationResult(
            job['run_id'], job['fault_id'], job['corner'], 'SIMULATION_ERROR',
            log_path=log_path, sim_time_s=time.time() - start,
            error_message='Aucun fichier .mt0 trouve.'
        )

    try:
        records = parse_all_records(testbench)
    except Exception as exc:
        return SimulationResult(
            job['run_id'], job['fault_id'], job['corner'], 'SIMULATION_ERROR',
            mt0_path=mt0_path, log_path=log_path,
            sim_time_s=time.time() - start, error_message=str(exc)
        )

    if not records:
        return SimulationResult(
            job['run_id'], job['fault_id'], job['corner'], 'SIMULATION_ERROR',
            mt0_path=mt0_path, log_path=log_path,
            sim_time_s=time.time() - start, error_message='Aucune mesure exploitable.'
        )

    return SimulationResult(
        job['run_id'], job['fault_id'], job['corner'], 'SUCCESS',
        measurements={'records': records}, mt0_path=mt0_path,
        log_path=log_path, sim_time_s=time.time() - start
    )


class SpectreRunner(object):
    def __init__(self, spectre_command='spectre', workers=10, timeout_seconds=600):
        self.spectre_command = spectre_command
        self.workers = int(workers)
        self.timeout_seconds = int(timeout_seconds)

    def run_jobs(self, jobs):
        prepared = []
        for job in jobs:
            item = dict(job)
            item['spectre_command'] = self.spectre_command
            item['timeout_seconds'] = self.timeout_seconds
            prepared.append(item)

        results = []
        with ProcessPoolExecutor(max_workers=self.workers) as executor:
            future_map = {executor.submit(_run_one, job): job for job in prepared}
            for future in as_completed(future_map):
                results.append(future.result())

        return results
