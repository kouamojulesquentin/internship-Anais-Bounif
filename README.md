# Framework d'injection de fautes analogiques — v2 (OPEN, SHORT, PARAMETRIC)

Outil d'injection de fautes physiques (circuits ouverts, courts-circuits) dans des
netlists SPICE/Spectre, avec simulation automatique sur 5 corners de process
(TT, FF, FS, SF, SS), verification par rapport a des specifications, et calcul
d'une couverture de test ponderee dans l'esprit de la norme IEEE Std 2427.

Pipeline : parsing de la netlist -> generation de l'univers de fautes ->
fusion des fautes redondantes (collapsing) -> injection physique -> generation
d'un testbench par corner -> simulation Spectre -> extraction des mesures
(.mt0/.mt1...) -> verification par rapport aux specs -> calcul de couverture ->
rapports CSV/JSON/SQLite.

---

## 1. Prerequis

- Spectre (Cadence) installe et accessible (`which spectre` doit repondre),
  avec une licence active dans l'environnement du terminal.
- Python 3.6 ou superieur, aucune dependance externe requise pour le coeur du
  framework (`pytest` est optionnel, seulement pour lancer les tests).
- Aucune installation du package n'est necessaire (`pip install -e .` n'est
  PAS requis) : les scripts de lancement gerent eux-memes le `PYTHONPATH`.

### Configurer l'acces a Spectre

Si votre `spectre` necessite de sourcer un script d'environnement avant d'etre
disponible dans le terminal (cas frequent avec les installations Cadence),
definissez la variable d'environnement `CADENCE_ENV_SCRIPT` **avant** de
lancer les scripts de ce projet, par exemple dans votre `~/.bashrc` :

```bash
export CADENCE_ENV_SCRIPT="$HOME/chemin/vers/votre/env_cadence.sh"
```

Si `spectre` est deja disponible dans votre `PATH` sans rien sourcer, ne
definissez rien : les scripts fonctionnent normalement sans cette variable.

**Piege frequent** : cette variable doit etre active dans CHAQUE terminal /
session `screen` / `tmux` que vous utilisez. Si vous obtenez
`spectre: commande introuvable` alors que vous avez deja lance une campagne
avec succes plus tot, c'est presque toujours parce que vous etes dans un
nouveau terminal ou `CADENCE_ENV_SCRIPT` n'a pas ete (re)source.

---

## 2. Demarrage rapide : tester sur l'exemple fourni

Le projet inclut un circuit `DEMO` totalement autonome (un simple filtre RC),
qui ne necessite aucun modele de fonderie particulier — utile pour verifier
que tout fonctionne avant de brancher votre propre circuit.

```bash
chmod +x test_circuit.sh run_all.sh run_campaign.py run_all.py
./test_circuit.sh DEMO smoke-gen   # generation seule, verifie que ca ne plante pas
./test_circuit.sh DEMO smoke       # Spectre reel, 3 fautes, corner TT
./test_circuit.sh DEMO             # campagne complete
cat results_demo/coverage_summary.json
```

Si ces 3 commandes fonctionnent, votre installation est prete.

---

## 3. Brancher VOTRE circuit — guide pas-a-pas

C'est le but principal de ce framework : tester un circuit qui n'a jamais ete
vu auparavant. Suivez ces etapes dans l'ordre ; ne sautez aucune verification,
chaque etape rattrape un probleme avant qu'il ne se propage a la suivante.

### Etape 1 — Preparer vos fichiers

Vous avez besoin, au minimum :
- Un fichier **netlist** (`.sub`) contenant au moins un bloc `.subckt ... .ends`
  avec vos composants (R, C, L, D, MOSFET, BJT, ou des sous-circuits X
  instanciant des modeles de votre PDK).
- Un fichier **testbench** (`.circuit`) qui instancie ce sous-circuit,
  applique des stimuli, et contient des instructions `.MEAS` pour mesurer ce
  qui vous interesse (gain, delai, offset, courant de repos, etc.).
- Si votre circuit utilise des modeles de fonderie specifiques (via des
  sous-circuits `X...`), le fichier de la librairie de modeles correspondant
  (equivalent a un `PRIMITIVE.sub`), inclus depuis votre testbench.
- Des fichiers de process pour vos 5 corners (`.process`), un par corner
  (`typical`, `fastN_fastP`, etc.) — si vous n'en avez qu'un seul pour
  commencer, vous pouvez tester avec `--only-corner TT` en attendant les
  autres.

### Etape 2 — Enregistrer le circuit

Ajoutez une entree dans `config/circuits.json` :

```json
{
  "MONCIRCUIT": {
    "netlist": "subcircuit_files/MONCIRCUIT.sub",
    "testbench": "MONCIRCUIT.circuit",
    "specs": "config/specs_moncircuit.json"
  }
}
```

Deux champs optionnels, utiles si votre circuit ne partage pas la config
utilisee par les autres (voir section 4 sur la portabilite du modele de
faute) :
- `"config"` : chemin vers un fichier framework alternatif (par defaut
  `config/framework.json`).
- `"process_dir"` : dossier de process alternatif (par defaut
  `process_models/`).

### Etape 3 — Generer sans simuler, et inspecter

```bash
./test_circuit.sh MONCIRCUIT smoke-gen
cat results_moncircuit/golden/TT/golden.circuit | grep INCLUDE
```

Verifiez que chaque chemin `.INCLUDE` affiche pointe vers un fichier qui
existe reellement (`ls -la <chemin>` sur chacun). C'est le moment de repérer
les erreurs de chemin avant de gaspiller du temps de simulation.

### Etape 4 — Lancer Spectre a la main sur le golden

```bash
cd results_moncircuit/golden/TT
spectre golden.circuit -raw golden.raw
cat golden.mt0
```

C'est l'etape la plus importante : elle revele les incompatibilites de
syntaxe AVANT de lancer des centaines de simulations. Voir section 6 pour les
erreurs les plus frequentes a ce stade.

Notez les noms EXACTS des mesures tels qu'ils apparaissent dans l'en-tete du
`.mt0` reel (pas forcement identiques a l'instruction `.MEAS` d'origine — la
casse ou des caracteres comme `%` ou `@` peuvent differer).

### Etape 5 — Ecrire les specs

Creez `config/specs_moncircuit.json` avec les bornes min/max de chaque
mesure, en utilisant les noms EXACTS reperes a l'etape precedente :

```json
{
  "nom_mesure_en_minuscules": {"min": -0.001, "max": 0.001}
}
```

### Etape 6 — Monter en echelle progressivement

```bash
./test_circuit.sh MONCIRCUIT smoke     # Spectre reel, 3 fautes, 1 corner
./test_circuit.sh MONCIRCUIT medium    # 10 fautes, 5 corners
./test_circuit.sh MONCIRCUIT           # campagne complete
```

Ne sautez pas directement a la campagne complete sur un circuit jamais teste
— un circuit de taille importante peut representer des milliers de
simulations.

---

## 4. Le modele de faute physique (portabilite entre fonderies)

Les courts-circuits et circuits ouverts sont materialises par une resistance
extreme plutot qu'un court/ouvert ideal (qui ferait diverger la simulation).
Deux modes sont disponibles, configures dans le fichier `framework.json` de
votre choix :

**Mode generique (par defaut recommande pour un nouveau circuit)**,
utilise une resistance SPICE ideale native, sans dependance a un PDK :
```json
"short_model": {"value": "1m"},
"open_model": {"value": "1T"}
```

**Mode avance (fonderie specifique)**, utilise un modele physique reel de
votre PDK (plus realiste, mais necessite que ce modele existe dans votre
librairie de primitives) :
```json
"short_model": {"primitive": "votre_modele_resistance", "L": "3.5e-6", "W": "2e-6", "M": "1"},
"open_model": {"primitive": "votre_modele_resistance", "L": "35", "W": "2e-6", "M": "1"}
```

`config/framework_generic.json` est fourni comme point de depart generique ;
`config/framework_ams_pdk_example.json` illustre le mode avance (exemple
documente, a adapter a votre propre PDK).

---

## 4bis. Fautes parametriques (deviation de valeur, optionnel)

En plus des fautes catastrophiques (OPEN/SHORT), le framework peut generer
des fautes parametriques : une deviation de +/-X% d'un parametre du
composant (valeur R/C/L, ou W/L pour un MOSFET, ou M pour un BJT), plutot
qu'un court-circuit ou une ouverture francs.

**Le pourcentage n'est pas impose par IEEE Std 2427** — cette norme specifie
la methode de comptage/reporting de la couverture, pas la magnitude des
fautes elle-meme. C'est un choix de methodologie : la litterature utilise
couramment entre +/-10% et +/-50% pour des fautes parametriques (a distinguer
des fautes quasi-catastrophiques, parfois modelisees a +/-75% ou plus). La
valeur par defaut de ce framework est +/-20%, ajustable dans `framework.json` :

```json
"enable_parametric_faults": true,
"parametric_deviation_pct": 20.0
```

Desactive par defaut (`false`) pour ne pas changer le comportement ni les
resultats d'une campagne existante sans action explicite. Si vous disposez de
vraies donnees de variation process de votre fonderie (ex: tolerance 3-sigma
mesuree en production), utilisez-les de preference a la valeur par defaut.

---

## 5. Raccourcis disponibles

| Commande | Fautes | Corners | Spectre reel ? |
|---|---|---|---|
| `smoke-gen` | 3 | TT seul | Non — genere les fichiers, ne simule pas |
| `smoke` | 3 | TT seul | Oui |
| `medium` | 10 | 5 (TT/FF/FS/SF/SS) | Oui |
| *(aucun argument)* | tous | 5 (TT/FF/FS/SF/SS) | Oui — campagne complete |

On peut aussi passer n'importe quelle option native de `main.py` directement :
```bash
./test_circuit.sh MONCIRCUIT --limit-faults 20 --only-corner FF
```

Pour lancer TOUS les circuits enregistres automatiquement, les uns apres les
autres, avec un resume comparatif a la fin :
```bash
./run_all.sh smoke-gen   # verification rapide de tous les circuits
./run_all.sh             # campagne complete sur TOUS les circuits
```

### Campagnes longues : utiliser `screen` ou `tmux`

Pour un circuit important (des milliers de simulations), `nohup ... &` seul
ne suffit pas toujours a proteger le calcul d'une deconnexion SSH (certains
systemes tuent les processus d'arriere-plan a la fin de la derniere session,
meme avec `nohup`). Utilisez plutot une session persistante :

```bash
screen -S ma_session
export CADENCE_ENV_SCRIPT="..."   # si necessaire, voir section 1
./test_circuit.sh MONCIRCUIT
# Ctrl+a puis d pour se detacher sans tuer le calcul
# Pour revenir plus tard : screen -r ma_session
```

---

## 6. Problemes frequents rencontres (et leurs solutions)

Ces pieges sont quasi systematiques a chaque nouveau circuit ; a verifier en
premier lors de l'etape 4 (Spectre a la main sur le golden).

### `.MEASURE: Unexpected value` sur des mots-cles `Lbound=`/`Ubound=`
Certains testbenchs (origine Eldo/HSPICE) utilisent une syntaxe de bornes
pass/fail que Spectre ne comprend pas. A retirer du testbench (le framework
verifie deja les bornes lui-meme via `specs.json`) :
```bash
sed -i -E 's/[[:space:]]+[Ll]bound=[^[:space:]]+[[:space:]]+[Uu]bound=[^[:space:]]+//' MONCIRCUIT.circuit
```

### `Unknown parameter '[nom_param]'` sur une substitution `{param}`
Spectre ne resout pas toujours une reference `{param}` definie via `.param`.
Remplacer par la valeur litterale directement :
```bash
sed -i 's/{nom_param}/valeur/g' MONCIRCUIT.circuit
```

### Chemins de fichiers avec des caracteres accentues
Si le dossier de travail contient des accents, Spectre peut corrompre le
chemin si la locale du terminal n'est pas UTF-8. Travaillez dans un chemin
sans accents ni caracteres speciaux.

### Circuit hierarchique (un `.sub` qui en inclut un autre)
Deja gere automatiquement : seul le fichier `.sub` correspondant au
`--netlist` demande est remplace par la version fautee, les autres `.sub`
inclus restent des dependances intactes.

### Fichiers verrouilles apres un arret brutal (NFS)
Un `rm -rf` peut echouer sur des dossiers `.ahdlSimDB` apres un `pkill -9` sur
spectre. Renommez le dossier (`mv`) plutot que de forcer la suppression, et
relancez sous un nouveau nom de resultats.

### Nom de mesure qui ne matche pas
Toujours verifier le nom EXACT tel qu'il apparait dans le vrai `.mt0` genere
par Spectre, pas le nom tel qu'ecrit dans l'instruction `.MEAS`.

---

## 7. Limitations connues du framework

- **Pas d'injection recursive dans les sous-circuits instancies.** Si votre
  circuit instancie un autre bloc, seuls les composants directement declares
  dans le `.sub` passe en `--netlist` sont fautes. Pour couvrir un bloc
  instancie, lancez une campagne separee sur son propre `.sub`.
- **Composants a plus de 2 bornes** (ex: resistances de diffusion 3 bornes) :
  seuls les deux premiers noeuds listes sont utilises pour generer les
  fautes OPEN/SHORT.
- **Bulk MOS ouvert et diodes de protection** sont structurellement difficiles
  a detecter par mesure de sortie seule — limitation physique/methodologique
  generale, pas un bug.
- **Un golden invalide dans un corner** (mesure hors specs) rend
  automatiquement toutes les fautes de ce corner `UNKNOWN`, par precaution.

---

## 8. Comprendre les fichiers de resultats

| Fichier | Contenu |
|---|---|
| `defect_universe.csv` | Liste complete des defauts generes, avec leur type (OPEN/SHORT) |
| `simulation_results.csv` | Statut de simulation + statut de detection + temps d'execution, une ligne par (faute, corner) |
| `spec_values.csv` | Valeur mesuree ET pass/fail pour CHAQUE spec, une ligne par simulation |
| `measurements_full.csv` | Toutes les mesures brutes disponibles (specs + sondes internes + mesures AC) |
| `coverage_summary.json` | Couverture globale (union), par corner, par type de faute |
| `simulation_results.db` | Meme contenu que le CSV principal, en base SQLite |

---

## 9. Lancer les tests de non-regression du framework

```bash
cd tests
python3 -m pytest .   # si pytest est installe
```
