# 🧮 irpp-mcp — Simulateur IRPP officiel DGFiP

Serveur MCP Python qui calcule l'impôt sur le revenu français à partir du **code source officiel DGFiP**, compilé via [Mlang (OCamlPro/DGFiP)](https://gitlab.adullact.net/dgfip/impots-nationaux-revenu-patrimoine-particuliers/Mlang). Calcul 100% local, zéro appel réseau.

**Revenus couverts : 2023** (déclaration 2024). Voir [Limitations](#limitations).

---

## Architecture

```
Sources DGFiP (langage M)  →  Mlang (OCamlPro/DGFiP)  →  C (~55 Mo)  →  irpp_calc
                                                                           ↓
                                                                    irpp_mcp.py (MCP)
                                                                           ↓
                                                                      Claude Code
```

---

## Arborescence attendue

Avant de commencer, créer un répertoire de travail. À la fin de l'installation, la structure sera :

```
~/impots/
├── calculette-ir-master/           ← sources DGFiP téléchargées (étape 1)
│   └── sources2023m_8_0/
├── mlang-src/                      ← compilateur Mlang cloné (étape 2)
│   ├── _build/default/src/main.exe
│   ├── m_ext/2023/
│   └── examples/dgfip_c/ml_primitif/c_driver/
│       └── irdata.c
├── output/                         ← C générés (étape 3) + binaire (étape 4)
│   ├── irpp_driver.c               ← fourni dans ce repo
│   ├── Makefile                    ← fourni dans ce repo
│   └── irpp_calc                   ← binaire compilé
└── irpp-mcp/                       ← ce repo (cloné en premier)
    └── irpp_mcp.py
```

**Commencer par cloner ce repo :**

```bash
mkdir ~/impots && cd ~/impots
git clone https://github.com/erwanpaccard/irpp-mcp.git
```

---

## Installation

### Prérequis

- WSL (Ubuntu 22.04 recommandé) — nécessaire pour compiler et exécuter le binaire Linux
- Python 3.11+ avec `pip`
- `gcc`, `make`, `git`, `opam`, `unzip`

---

### Étape 1 — Sources DGFiP (langage M)

Le code fiscal officiel est publié par la DGFiP sur Adullact sous licence CeCILL 2.1. Aucun compte requis.

```bash
cd ~/impots
curl -L "https://gitlab.adullact.net/dgfip/impots-nationaux-revenu-patrimoine-particuliers/calculette-ir/-/archive/master/calculette-ir-master.zip" \
     -o calculette-ir-master.zip
unzip calculette-ir-master.zip
```

Dossier utile : `calculette-ir-master/sources2023m_8_0/`

---

### Étape 2 — Compiler Mlang (~15 min)

```bash
cd ~/impots
sudo apt install libgmp-dev libmpfr-dev git opam bubblewrap unzip bzip2 patch

git clone https://gitlab.adullact.net/dgfip/impots-nationaux-revenu-patrimoine-particuliers/Mlang.git mlang-src
cd mlang-src

# Correctif obligatoire (version non substituée dans les fichiers opam)
sed -i 's/%%VERSION%%/0.0.1/g' mlang.opam irj_checker.opam

OPAMYES=1 make init
make build
```

Binaire produit : `mlang-src/_build/default/src/main.exe`

---

### Étape 3 — Générer les fichiers C depuis les sources M

```bash
cd ~/impots/mlang-src
eval $(opam env --switch=$(pwd) --set-switch)

./_build/default/src/main.exe \
  -A iliad \
  --display_time \
  --precision double \
  --mpp_function=enchainement_primitif \
  --income-year=2023 \
  --dgfip_options=-g,-O,-k4,-m2023,-X \
  --backend dgfip_c \
  --output ../output/irpp_2023.c \
  $(find ../calculette-ir-master/sources2023m_8_0 -name 'tgvI.m') \
  $(find ../calculette-ir-master/sources2023m_8_0 -name 'errI.m') \
  $(find ../calculette-ir-master/sources2023m_8_0 -name '*.m' \
    ! -name 'err*.m' ! -name 'tgv*.m' ! -name 'cibles.m' | sort) \
  m_ext/2023/cibles.m m_ext/2023/codes_1731.m m_ext/2023/commence_par_5.m \
  m_ext/2023/commence_par_7.m m_ext/2023/commence_par_H.m \
  m_ext/2023/correctif.m m_ext/2023/main.m
```

> `tgvI.m` doit être passé en premier — il déclare l'application `iliad`.

Résultat : ~55 Mo de fichiers C dans `~/impots/output/`.

---

### Étape 4 — Compiler le binaire

`irpp_driver.c` et `Makefile` sont déjà dans `output/` (fournis par ce repo). Copier depuis le repo :

```bash
cp ~/impots/irpp-mcp/output/irpp_driver.c ~/impots/output/
cp ~/impots/irpp-mcp/output/Makefile ~/impots/output/

cd ~/impots/output
make CDRIVER=../mlang-src/examples/dgfip_c/ml_primitif/c_driver
```

Tester :

```bash
printf "V_0AC=1\nTSHALLOV=50000.00\n" | ./irpp_calc
# → {"IINET": 6786.00, "NBPT": 1.00, "RNI": 45000.00, ...}
```

---

### Étape 5 — Installer le serveur MCP

```bash
pip install mcp pydantic
```

Vérifier que `BINARY_PATH` dans `irpp_mcp.py` pointe vers le binaire compilé. Par défaut :

```python
BINARY_PATH = Path(__file__).parent.parent / "output" / "irpp_calc"
# → ~/impots/output/irpp_calc  ✓ si vous avez suivi l'arborescence ci-dessus
```

---

### Étape 6 — Configurer Claude Code

Créer `.mcp.json` à la racine du projet Claude Code :

```json
{
  "mcpServers": {
    "irpp-mcp": {
      "command": "python3",
      "args": ["/home/user/impots/irpp-mcp/irpp_mcp.py"]
    }
  }
}
```

Sur Windows (invocation via WSL) :

```json
{
  "mcpServers": {
    "irpp-mcp": {
      "command": "wsl",
      "args": ["-e", "python3", "/mnt/c/Users/vous/impots/irpp-mcp/irpp_mcp.py"]
    }
  }
}
```

> Adapter le chemin à votre arborescence. Trouver le chemin Python : `which python3` dans WSL.

---

## Utilisation

L'outil MCP `irpp_calculer_ir` accepte les paramètres du formulaire 2042 :

| Paramètre | Case 2042 | Description |
|-----------|-----------|-------------|
| `situation` | — | `celibataire` / `marie` / `pacse` / `divorce` / `veuf` |
| `salaires_declarant1` | 1AJ | Salaires nets imposables déclarant 1 |
| `salaires_declarant2` | 1BJ | Salaires nets imposables déclarant 2 |
| `pensions_declarant1` | 1AS | Pensions, retraites, rentes déclarant 1 |
| `pensions_declarant2` | 1BS | Pensions, retraites, rentes déclarant 2 |
| `bnc_declarant1` | 5QC | BNC professionnels régime normal |
| `micro_foncier` | 4BE | Micro-foncier recettes brutes |
| `dividendes` | 2DC | Dividendes (abattement 40 %) |
| `plus_values` | 3VG | Plus-values mobilières |
| `nb_enfants_charge` | 0CF | Enfants mineurs à charge |
| `nb_enfants_alternee` | 0CH | Enfants en résidence alternée |
| `per_declarant1` | 6NS | Cotisations PER déductibles déclarant 1 |
| `per_declarant2` | 6NT | Cotisations PER déductibles déclarant 2 |
| `pension_alimentaire` | 6GI | Pension alimentaire versée à enfant majeur |
| `revenus_fonciers_reels` | 4BA | Revenus fonciers nets régime réel |
| `annee_naissance_declarant1` | — | Année de naissance déclarant 1 |
| `response_format` | — | `markdown` (défaut) ou `json` |

Variables retournées : `IINET` (impôt net), `NBPT` (parts), `RNI` (revenu net imposable), `REVKIRE` (revenu fiscal de référence), `IRNET`, `IAVIM`, `IRTOTAL`.

---

## Utilisation avec le skill impôts

Le skill [erwanpaccard/impots](https://github.com/erwanpaccard/impots) détecte automatiquement ce serveur MCP et l'utilise pour les simulations IR — les calculs s'appuient alors sur le moteur DGFiP officiel plutôt que sur des estimations LLM.

---

## Limitations

- **Revenus 2023 uniquement** : les sources 2024 (`sources2024m_3_13`) sont incompatibles avec la version actuelle de Mlang (variable `GLOBAL.REPRCM` non résolue dans le contexte `correctif`).
- **`micro_bnc_declarant1` (case 5TE)** : calcule `REVKIRE` correctement mais donne `IINET=0`. Workaround : passer les recettes × 66 % dans `bnc_declarant1` (5QC).
- **Binaire Linux uniquement** : sur Windows, l'invocation passe automatiquement par WSL.

---

## Sources et licences

| Composant | Source | Licence |
|-----------|--------|---------|
| Sources DGFiP (revenus 2023) | [Adullact — calculette-ir](https://gitlab.adullact.net/dgfip/impots-nationaux-revenu-patrimoine-particuliers/calculette-ir) | CeCILL 2.1 |
| Compilateur Mlang | [Mlang (Adullact)](https://gitlab.adullact.net/dgfip/impots-nationaux-revenu-patrimoine-particuliers/Mlang) | GPL-3.0 |
| `irpp_driver.c` + `irpp_mcp.py` | Ce dépôt | MIT |
