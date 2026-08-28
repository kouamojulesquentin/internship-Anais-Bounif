#!/bin/bash
# Lance la campagne sur TOUS les circuits enregistres, automatiquement.
# Usage:
#   ./run_all.sh              -> campagne COMPLETE sur chaque circuit
#   ./run_all.sh smoke        -> smoke test rapide sur chaque circuit
#   ./run_all.sh smoke-gen    -> generation seule (pas de Spectre) sur chaque circuit
#
# Voir test_circuit.sh pour la configuration de l'environnement Spectre/Cadence
# (variable CADENCE_ENV_SCRIPT).

if [ -n "$CADENCE_ENV_SCRIPT" ] && [ -f "$CADENCE_ENV_SCRIPT" ]; then
    source "$CADENCE_ENV_SCRIPT"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/run_all.py" "$@"
