# Démo — Utiliser le framework 

Ce guide montre comment lancer le framework de bout en bout sur un circuit
totalement autonome (`DEMO`, un simple filtre RC passe-bas), fourni avec le
dépôt. 

---

## 1. Prérequis

- Spectre (Cadence) installé et accessible .
- Python 3.6+. 

Si `spectre` nécessite de sourcer un script d'environnement avant d'être
disponible dans le terminal :

```bash
export CADENCE_ENV_SCRIPT="/chemin/vers/votre/env_cadence.sh"
```

---

## 2. Récupérer le projet

```bash
git clone <url-du-depot>
cd framework_version_finale
chmod +x test_circuit.sh run_all.sh run_campaign.py run_all.py
```

---

## 3. Le circuit de démonstration

Le dossier `examples/demo/` contient un filtre RC minimal :

```
examples/demo/
├── DEMO.circuit                    <- testbench (stimulus + mesures)
├── subcircuit_files/DEMO.sub       <- netlist : R1 + C1
└── process_models/                 <- fichiers de corner (placeholders,
                                        inutiles ici car pas de transistor)
```

Contenu de `DEMO.sub` :

```spice
.subckt DEMO vin vout gnd
R1 vin vout 1k
C1 vout gnd 1u
.ends
```

Un filtre RC passe-bas classique, fréquence de coupure théorique
≈ 159 Hz (`1 / (2π·R·C)`).

---

## 4. Étape 1 — Génération seule (aucun appel à Spectre)

```bash
./test_circuit.sh DEMO smoke-gen
```

Sortie réelle obtenue :

```
>>> Circuit: DEMO
>>> --netlist .../examples/demo/subcircuit_files/DEMO.sub
    --testbench .../examples/demo/DEMO.circuit
    --specs .../examples/demo/specs_demo.json
    --config .../config/framework_generic.json
    --process-dir .../examples/demo/process_models
    --results .../results_demo
    --limit-faults 3 --only-corner TT --generate-only

Mode smoke test: limite a 3 fautes.
Sous-circuits : 1
Composants    : 2
Defauts       : 3
Golden jobs   : 1
Fault jobs    : 3
Generation terminee; Spectre non lance.
```

Le framework a reconnu les deux composants (`R1`, `C1`) et généré
l'univers de défauts correspondant. Vérification systématique avant
d'aller plus loin — les chemins `.INCLUDE` du testbench généré :

```bash
cat results_demo/golden/TT/golden.circuit | grep INCLUDE
```

```
.INCLUDE golden.sub
```

Une seule ligne — aucune dépendance à un fichier de modèles de fonderie,
puisque `R1`/`C1` sont des composants SPICE natifs.

---

## 5. Étape 2 — Inspecter les fautes générées

```bash
cat results_demo/defect_universe.csv
```

4 défauts générés à partir des 2 composants (1 SHORT + 1 OPEN par
composant) :

| fault_id | fault_type |
|---|---|
| `DEMO__R1__SHORT` | SHORT |
| `DEMO__R1__OPEN` | OPEN |
| `DEMO__C1__SHORT` | SHORT |
| `DEMO__C1__OPEN` | OPEN |

Exemple de netlist injectée (`DEMO__R1__OPEN`) — R1 est coupé et remplacé
par une résistance de fuite très haute impédance :

```spice
.subckt DEMO vin vout gnd
R1 __open_R1_1 vout 1k
R_xr_fault vin __open_R1_1 1T
C1 vout gnd 1u
.ends
```

---

## 6. Étape 3 — Lancer Spectre à la main sur le golden

Étape essentielle avant toute campagne : vérifier que le testbench
converge, et repérer les incompatibilités de syntaxe éventuelles.

```bash
cd results_demo/golden/TT
spectre golden.circuit -raw golden.raw
cat golden.mt0
```

Notez les noms de mesures exacts affichés dans le `.mt0` — ce sont ceux à
utiliser dans le fichier de specs (`examples/demo/specs_demo.json`).

---

## 7. Étape 4 — Smoke test réel, puis campagne complète

```bash
cd ../../..
./test_circuit.sh DEMO smoke      # Spectre reel, 3 fautes, corner TT
./test_circuit.sh DEMO            # campagne complete (tous les corners)
cat results_demo/coverage_summary.json
```

---

## 8. Brancher son propre circuit

La même procédure s'applique à n'importe quel circuit, générique ou
spécifique à une fonderie. Voir la section 3 du `README.md` du dépôt pour
le guide détaillé pas-à-pas ("Brancher VOTRE circuit").

En résumé : deux fichiers à fournir, aucun code à écrire.

```json
// config/circuits.json
{
  "MONCIRCUIT": {
    "netlist": "subcircuit_files/MONCIRCUIT.sub",
    "testbench": "MONCIRCUIT.circuit",
    "specs": "config/specs_moncircuit.json"
  }
}
```

```json
// config/specs_moncircuit.json
{
  "nom_mesure": {"min": -0.001, "max": 0.001}
}
```

Puis :

```bash
./test_circuit.sh MONCIRCUIT smoke-gen
```

---

## 9. Récapitulatif des commandes

| Commande | Effet |
|---|---|
| `./test_circuit.sh NOM smoke-gen` | Génère les fichiers, ne simule pas |
| `./test_circuit.sh NOM smoke` | Simule 3 fautes, corner TT |
| `./test_circuit.sh NOM medium` | Simule 10 fautes, 5 corners |
| `./test_circuit.sh NOM` | Campagne complète |
| `./run_all.sh` | Campagne complète sur tous les circuits enregistrés |


