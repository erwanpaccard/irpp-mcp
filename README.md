# irpp-mcp — Simulateur IRPP officiel DGFiP

Calcule l'impôt sur le revenu avec le **code source officiel DGFiP**, compilé via
[Mlang](https://github.com/MLanguage/mlang) (INRIA). Calcul 100% local, zéro appel réseau.

## Architecture de la chaîne

```
Sources DGFiP (langage M)    →    Mlang (compilateur OCaml)    →    Fichiers C (~55 Mo)
        ↓                                                                    ↓
  Adullact / GitLab                   GitHub INRIA                  gcc → irpp_calc
                                                                          ↓
                                                               Python MCP (irpp_mcp.py)
                                                                          ↓
                                                                    Claude Code
```

---

## Étape 1 — Obtenir les sources DGFiP (langage M)

Le code fiscal officiel est publié par la DGFiP sur Adullact sous licence **CeCILL 2.1**.
Pas de compte requis pour le téléchargement.

```bash
# Depuis WSL ou Linux
curl -L "https://gitlab.adullact.net/dgfip/impots-nationaux-revenu-patrimoine-particuliers/calculette-ir/-/archive/master/calculette-ir-master.zip" \
     -o calculette-ir-master.zip
unzip calculette-ir-master.zip
```

Structure utile dans l'archive :
```
calculette-ir-master/
  sources2023m_8_0/   ← revenus 2023 (déclaration 2024)  ← utilisé ici
  sources2024m_3_13/  ← revenus 2024 (incompatible avec m_ext Mlang, voir Limitations)
```

---

## Étape 2 — Compiler Mlang (compilateur M → C)

Mlang est le compilateur open-source (OCaml, INRIA) qui traduit le langage M DGFiP en C.
Il fournit aussi les fichiers `m_ext/` (point d'entrée) et le driver C (`c_driver/`).

**Dépôt** : https://github.com/MLanguage/mlang

### 2a. Installer les dépendances (WSL Ubuntu 22.04)

```bash
sudo apt install libgmp-dev libmpfr-dev git opam bubblewrap unzip bzip2 patch
```

### 2b. Cloner et compiler (~15-20 min)

```bash
git clone https://github.com/MLanguage/mlang.git mlang-src
cd mlang-src

# Correctif obligatoire : la version n'est pas substituée dans les fichiers opam
sed -i 's/%%VERSION%%/0.0.1/g' mlang.opam irj_checker.opam

OPAMYES=1 make init
make build
```

Le compilateur est produit dans `mlang-src/_build/default/src/main.exe`.

---

## Étape 3 — Générer les fichiers C depuis les sources M

Cette commande lance Mlang sur les sources DGFiP et génère ~55 Mo de fichiers C dans `output/`.

```bash
# Depuis le répertoire mlang-src
cd mlang-src
eval $(opam env --switch=$(pwd) --set-switch)

# Adapter ces chemins à votre arborescence
SOURCES='../calculette-ir-master/sources2023m_8_0'
MEXT='m_ext/2023'          # fourni dans mlang-src, pas dans calculette-ir
YEAR=2023
OUTPUT_DIR='../output'

mkdir -p $OUTPUT_DIR

./_build/default/src/main.exe \
  -A iliad \
  --display_time \
  --precision double \
  --mpp_function=enchainement_primitif \
  --income-year=$YEAR \
  --dgfip_options=-g,-O,-k4,-m$YEAR,-X \
  --backend dgfip_c \
  --output $OUTPUT_DIR/irpp_2023.c \
  $(find $SOURCES -name 'tgvI.m') $(find $SOURCES -name 'errI.m') \
  $(find $SOURCES -name '*.m' ! -name 'err*.m' ! -name 'tgv*.m' ! -name 'cibles.m' | sort) \
  $MEXT/cibles.m $MEXT/codes_1731.m $MEXT/commence_par_5.m \
  $MEXT/commence_par_7.m $MEXT/commence_par_H.m \
  $MEXT/correctif.m $MEXT/main.m
```

> **Important** : `tgvI.m` doit être passé en premier (il déclare l'application `iliad`).
> L'ordre des fichiers M est déterministe.

Fichiers produits dans `output/` :
```
mlang.c / mlang.h          ← runtime Mlang
varinfos.c / varinfo_0..8.c ← métadonnées variables DGFiP
m_chap-*.c                 ← chapitres du calcul (revenus, déductions, QF…)
m_cibles.c / m_main.c      ← orchestration
compir_*.c                 ← calculs IR spécifiques
irpp_2023.c                ← point d'entrée généré
```

---

## Étape 4 — Compiler le binaire `irpp_calc`

`irpp_driver.c` (fourni dans ce dépôt) est un driver stdin/stdout qui :
- lit des paires `VARIABLE=valeur` depuis stdin
- appelle la fonction principale DGFiP `enchainement_primitif_interpreteur`
- retourne les résultats clés en JSON sur stdout

`irdata.c` vient du répertoire `c_driver/` de Mlang et fournit les fonctions de gestion
des erreurs DGFiP (`finalise_erreur`, `exporte_erreur`).

```bash
# Depuis WSL, adapter les chemins
OUTPUT_DIR='/chemin/absolu/vers/output'
CDRIVER='/chemin/absolu/vers/mlang-src/examples/dgfip_c/ml_primitif/c_driver'

cd $OUTPUT_DIR
cp /chemin/vers/irpp-mcp/../irpp_driver.c .   # ou il est déjà là si vous avez cloné ce dépôt

gcc -std=c99 -O1 -I. \
  irpp_driver.c mlang.c varinfos.c varinfo_0.c varinfo_1.c varinfo_2.c \
  varinfo_3.c varinfo_4.c varinfo_5.c varinfo_6.c varinfo_7.c varinfo_8.c \
  m_main.c m_cibles.c m_chap-*.c m_codes_1731.c m_commence_par_5.c \
  m_commence_par_7.c m_commence_par_H.c m_correctif.c m_horizoc.c \
  m_horizoi.c m_res-ser1.c m_res-ser2.c m_coc1.c m_coc2.c m_coc3.c \
  m_coc4.c m_coc5.c m_coc7.c m_coi1.c m_coi2.c m_coi3.c \
  compir_contexte.c compir_famille.c compir_penalite.c compir_restitue.c \
  compir_revcor.c compir_revenu.c compir_tableg.c compir_tableg01.c \
  compir_tableg02.c compir_tableg03.c compir_tableg04.c compir_tablev.c \
  compir_variatio.c erreurs.c irpp_2023.c \
  $CDRIVER/irdata.c \
  -o irpp_calc -lm
```

Tester :
```bash
echo "V_0AC=1
TSHALLOV=50000.00" | ./irpp_calc
# → {"IINET":6786.0,"NBPT":1.0,"RNI":45000.0,...}
```

Le binaire est un ELF Linux 64-bit. Sur Windows, l'invocation passe par WSL
(géré automatiquement par `irpp_mcp.py`).

---

## Étape 5 — Installer le MCP Python

### 5a. Dépendances Python

```bash
pip install mcp pydantic
```

### 5b. Vérifier le chemin du binaire

Dans `irpp_mcp.py`, la constante `BINARY_PATH` pointe vers le binaire compilé :
```python
BINARY_PATH = Path(__file__).parent.parent / "output" / "irpp_calc"
```
Adapter si votre arborescence diffère.

### 5c. Configurer Claude Code

Créer `.mcp.json` à la racine du projet Claude Code :

```json
{
  "mcpServers": {
    "irpp-mcp": {
      "command": "python",
      "args": ["/chemin/absolu/vers/irpp-mcp/irpp_mcp.py"]
    }
  }
}
```

Sur Windows, utiliser le chemin complet vers Python et le script :
```json
{
  "mcpServers": {
    "irpp-mcp": {
      "command": "C:\\Python314\\python.exe",
      "args": ["C:\\chemin\\vers\\irpp-mcp\\irpp_mcp.py"]
    }
  }
}
```

Claude Code détecte automatiquement `.mcp.json` à l'ouverture du projet.

---

## Utilisation

L'outil MCP `irpp_calculer_ir` accepte les paramètres du formulaire 2042 :

| Paramètre | Case 2042 | Description |
|-----------|-----------|-------------|
| `situation` | 0AC/0AM/0AO/0AD/0AV | celibataire / marie / pacse / divorce / veuf |
| `salaires_declarant1` | 1AJ | Salaires nets imposables déclarant 1 |
| `salaires_declarant2` | 1BJ | Salaires nets imposables déclarant 2 |
| `pensions_declarant1` | 1AS | Pensions, retraites, rentes déclarant 1 |
| `pensions_declarant2` | 1BS | Pensions, retraites, rentes déclarant 2 |
| `bnc_declarant1` | 5QC | BNC professionnels régime normal |
| `micro_bnc_declarant1` | 5TE | Micro-entrepreneur BNC recettes brutes ⚠️ |
| `micro_foncier` | 4BE | Micro-foncier recettes brutes |
| `dividendes` | 2DC | Dividendes (abattement 40 %) |
| `plus_values` | 3VG | Plus-values mobilières |
| `nb_enfants_charge` | 0CF | Enfants mineurs à charge |
| `nb_enfants_alternee` | 0CH | Enfants en résidence alternée |
| `per_declarant1` | 6NS | Cotisations PER déductibles déclarant 1 |
| `per_declarant2` | 6NT | Cotisations PER déductibles déclarant 2 |
| `pension_alimentaire` | 6GI | Pension alimentaire versée à enfant majeur |
| `revenus_fonciers_reels` | 4BA | Revenus fonciers nets régime réel (bénéfice uniquement) |
| `annee_naissance_declarant1` | — | Année de naissance déclarant 1 |
| `response_format` | — | `markdown` (défaut) ou `json` |

Variables retournées : `IINET` (impôt net), `NBPT` (parts), `RNI` (revenu net imposable),
`REVKIRE` (revenu fiscal de référence), `IRNET`, `IAVIM`, `IRTOTAL`.

> ⚠️ **Limitation connue** : `micro_bnc_declarant1` (case 5TE) calcule `REVKIRE` correctement
> mais donne `IINET=0`. Workaround : passer les recettes × 66 % dans `bnc_declarant1` (5QC).

---

## Sources et licences

| Composant | Source | Licence |
|-----------|--------|---------|
| Sources DGFiP (langage M, revenus 2023) | [Adullact — calculette-ir](https://gitlab.adullact.net/dgfip/impots-nationaux-revenu-patrimoine-particuliers/calculette-ir) | CeCILL 2.1 |
| Compilateur Mlang | [GitHub — MLanguage/mlang](https://github.com/MLanguage/mlang) | GPL-3.0 |
| Driver MCP Python (`irpp_mcp.py`) | Ce dépôt | MIT |

- Revenus couverts : **2023** (déclaration 2024)
- Version sources DGFiP : `sources2023m_8_0`
