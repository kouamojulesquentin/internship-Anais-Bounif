#!/bin/bash
# Lance une analyse Monte Carlo de rendement sur un circuit.
# Usage:
#   ./run_monte_carlo.sh --netlist ... --testbench ... --specs ... \
#       --config ... --process-dir ... --results ... \
#       --num-trials 200 --sigma-pct 10 --corner TT [--seed 42]
#
# Voir test_circuit.sh pour la configuration de l'environnement Spectre/Cadence
# (variable CADENCE_ENV_SCRIPT).

if [ -n "$CADENCE_ENV_SCRIPT" ] && [ -f "$CADENCE_ENV_SCRIPT" ]; then
    source "$CADENCE_ENV_SCRIPT"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/monte_carlo_main.py" "$@"
