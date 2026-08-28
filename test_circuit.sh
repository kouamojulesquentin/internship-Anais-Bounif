#!/bin/bash
# Point d'entree unique pour tester un circuit.
# Usage: ./test_circuit.sh <NOM_CIRCUIT> [smoke|smoke-gen|medium|full|options main.py...]
#
# Exemples:
#   ./test_circuit.sh BANDGAP1 smoke-gen   -> generation seule, 3 fautes, corner TT
#   ./test_circuit.sh BANDGAP1 smoke       -> Spectre reel, 3 fautes, corner TT
#   ./test_circuit.sh BANDGAP1 medium      -> Spectre reel, 10 fautes, 5 corners
#   ./test_circuit.sh BANDGAP1             -> campagne complete
#   ./test_circuit.sh                      -> liste les circuits disponibles
#
# Environnement Spectre/Cadence :
# Si votre commande `spectre` necessite de sourcer un script d'environnement
# avant d'etre disponible dans le terminal, indiquez son chemin dans la
# variable d'environnement CADENCE_ENV_SCRIPT avant de lancer ce script,
# par exemple dans votre ~/.bashrc :
#     export CADENCE_ENV_SCRIPT="$HOME/mon_env_cadence/env.sh"
# Sinon, si `spectre` est deja dans votre PATH sans rien sourcer, ne touchez
# a rien : ce script continue normalement sans variable definie.

if [ -n "$CADENCE_ENV_SCRIPT" ] && [ -f "$CADENCE_ENV_SCRIPT" ]; then
    source "$CADENCE_ENV_SCRIPT"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/run_campaign.py" "$@"
