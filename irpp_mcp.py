#!/usr/bin/env python3
"""
irpp_mcp — Simulateur IRPP officiel DGFiP (revenus 2023)

Utilise le code C généré par Mlang depuis les sources DGFiP officielles.
Aucun appel réseau — calcul 100% local, code source authentique DGFiP.
"""

import asyncio
import json
import os
import platform
import sys
import tempfile
from enum import StrEnum
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ─── Configuration ────────────────────────────────────────────────────────────

BINARY_PATH = Path(__file__).parent.parent / "output" / "irpp_calc"

# Variables DGFiP → alias formulaire 2042
VARS_SITUATION = {
    "celibataire": "V_0AC",
    "divorce": "V_0AD",
    "marie": "V_0AM",
    "pacse": "V_0AO",
    "veuf": "V_0AV",
}

VARS_MAP: dict[str, str] = {
    "salaires_declarant1": "TSHALLOV",  # 1AJ
    "salaires_declarant2": "TSHALLOC",  # 1BJ
    "pensions_declarant1": "PRBRV",  # 1AS
    "pensions_declarant2": "PRBRC",  # 1BS
    "bnc_declarant1": "BNCREV",  # 5QC
    "micro_bnc_declarant1": "AUTOBNCV",  # 5TE (⚠️ bug connu: RNI=0)
    "micro_foncier": "RFMIC",  # 4BE
    "dividendes": "RCMABD",  # 2DC
    "plus_values": "BPVRCM",  # 3VG
    "annee_naissance_declarant1": "V_0DA",
    "annee_naissance_declarant2": "V_0DB",
    "nb_enfants_charge": "V_0CF",
    "nb_enfants_alternee": "V_0CH",
    "per_declarant1": "COD6NS",  # 6NS
    "per_declarant2": "COD6NT",  # 6NT
    "pension_alimentaire": "CHENF1",  # 6GI
    "revenus_fonciers_reels": "RFORDI",  # 4BA
}

# ─── Modèles ──────────────────────────────────────────────────────────────────


class SituationFamille(StrEnum):
    celibataire = "celibataire"
    marie = "marie"
    pacse = "pacse"
    divorce = "divorce"
    veuf = "veuf"


class ResponseFormat(StrEnum):
    markdown = "markdown"
    json = "json"


class CalculerIRInput(BaseModel):
    """Paramètres pour le calcul de l'impôt sur le revenu 2023."""

    model_config = ConfigDict(extra="ignore")

    situation: SituationFamille = Field(
        ...,
        description="Situation de famille : celibataire, marie, pacse, divorce, veuf",
    )
    salaires_declarant1: float = Field(
        default=0,
        ge=0,
        description="Salaires nets imposables déclarant 1 (case 1AJ), en euros",
    )
    salaires_declarant2: float = Field(
        default=0,
        ge=0,
        description="Salaires nets imposables déclarant 2 (case 1BJ), en euros",
    )
    pensions_declarant1: float = Field(
        default=0,
        ge=0,
        description="Pensions, retraites, rentes déclarant 1 (case 1AS), en euros",
    )
    pensions_declarant2: float = Field(
        default=0,
        ge=0,
        description="Pensions, retraites, rentes déclarant 2 (case 1BS), en euros",
    )
    bnc_declarant1: float = Field(
        default=0,
        ge=0,
        description="BNC professionnels régime normal déclarant 1 (case 5QC), en euros",
    )
    micro_bnc_declarant1: float = Field(
        default=0,
        ge=0,
        description="Micro-entrepreneur BNC recettes brutes déclarant 1 (case 5TE), en euros. "
        "⚠️ Limitation connue : calcule le revenu fiscal de référence mais pas l'impôt. "
        "Workaround : passer recettes × 66 % dans bnc_declarant1.",
    )
    micro_foncier: float = Field(
        default=0,
        ge=0,
        description="Micro-foncier recettes brutes (case 4BE), en euros",
    )
    dividendes: float = Field(
        default=0,
        ge=0,
        description="Dividendes ouvrant droit à abattement (case 2DC), en euros",
    )
    plus_values: float = Field(
        default=0,
        ge=0,
        description="Plus-values mobilières sans abattement (case 3VG), en euros",
    )
    annee_naissance_declarant1: int = Field(
        default=1975,
        ge=1900,
        le=2010,
        description="Année de naissance du déclarant 1 (ex: 1985)",
    )
    annee_naissance_declarant2: int | None = Field(
        default=None,
        ge=1900,
        le=2010,
        description="Année de naissance du déclarant 2 (ex: 1968). Laisser vide si pas de déclarant 2.",
    )
    nb_enfants_charge: int = Field(
        default=0,
        ge=0,
        le=20,
        description="Nombre d'enfants mineurs à charge (case 0CF)",
    )
    nb_enfants_alternee: int = Field(
        default=0,
        ge=0,
        le=20,
        description="Nombre d'enfants en résidence alternée (case 0CH)",
    )
    per_declarant1: float = Field(
        default=0,
        ge=0,
        description="Cotisations PER déductibles déclarant 1 (case 6NS), en euros",
    )
    per_declarant2: float = Field(
        default=0,
        ge=0,
        description="Cotisations PER déductibles déclarant 2 (case 6NT), en euros",
    )
    pension_alimentaire: float = Field(
        default=0,
        ge=0,
        description="Pension alimentaire versée à enfant majeur (case 6GI), en euros",
    )
    revenus_fonciers_reels: float = Field(
        default=0,
        ge=0,
        description="Revenus fonciers nets (régime réel, case 4BA), en euros. "
        "Valeur positive = bénéfice, négatif non supporté (passer 0 pour déficit).",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.markdown,
        description="Format de réponse : 'markdown' (par défaut) ou 'json'",
    )


# ─── Logique métier ───────────────────────────────────────────────────────────


def _win_to_wsl(path: Path) -> str:
    """Convertit un chemin Windows en chemin WSL (/mnt/drive/...)."""
    s = str(path.resolve())
    return f"/mnt/{s[0].lower()}/{s[2:].replace(chr(92), '/')}"


def _per_ceiling(income: float) -> float:
    """Plafond PER 2023 : 10% du revenu net, min 4 399 €, max 35 194 € (8× PASS)."""
    if income <= 0:
        return 4399.0
    return round(max(min(income * 0.10, 35194.0), 4399.0), 2)


def _build_stdin(situation: str, params: CalculerIRInput) -> str:
    lines = [f"{VARS_SITUATION[situation]}=1"]
    for field_name, dgfip_var in VARS_MAP.items():
        val = getattr(params, field_name, None)
        if val:
            lines.append(f"{dgfip_var}={float(val):.2f}")

    # PER : le moteur DGFiP exige V_BTPERPTOTV/C (plafond disponible N-1).
    # Sans cette variable le plafond vaut 0 et la déduction est annulée.
    # On calcule le plafond légal 2023 depuis les revenus courants (cas simplifié :
    # pas de report des années précédentes).
    if params.per_declarant1 > 0:
        income1 = (
            params.salaires_declarant1 * 0.9
            + params.pensions_declarant1 * 0.9
            + params.bnc_declarant1
        )
        lines.append(f"V_BTPERPTOTV={_per_ceiling(income1):.2f}")
    if params.per_declarant2 > 0:
        income2 = params.salaires_declarant2 * 0.9 + params.pensions_declarant2 * 0.9
        lines.append(f"V_BTPERPTOTC={_per_ceiling(income2):.2f}")

    return "\n".join(lines) + "\n"


async def _run_binary(stdin_data: str) -> dict:
    """Exécute irpp_calc de façon non-bloquante et retourne le JSON parsé."""
    if not BINARY_PATH.exists():
        raise FileNotFoundError(
            f"Binaire irpp_calc introuvable : {BINARY_PATH}\n"
            "Compilez-le depuis WSL (voir output/irpp_driver.c)"
        )

    is_windows = platform.system() == "Windows"

    def _run_sync() -> str:
        import subprocess

        if is_windows:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(stdin_data)
                tmp_win = f.name
            try:
                tmp_wsl = _win_to_wsl(Path(tmp_win))
                bin_wsl = _win_to_wsl(BINARY_PATH)
                r = subprocess.run(
                    ["wsl", "-e", "bash", "-c", f"{bin_wsl} < {tmp_wsl}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            finally:
                os.unlink(tmp_win)
        else:
            r = subprocess.run(
                [str(BINARY_PATH)],
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=15,
            )
        if r.returncode != 0:
            raise RuntimeError(f"Calcul DGFiP échoué : {r.stderr.strip()}")
        return r.stdout

    stdout = await asyncio.to_thread(_run_sync)
    return json.loads(stdout)


def _format_markdown(results: dict, params: CalculerIRInput) -> str:
    iinet = results.get("IINET", 0)
    nbpt = results.get("NBPT", 0)
    rni = results.get("RNI", 0)
    revkire = results.get("REVKIRE", 0)

    txmoy = (iinet / revkire * 100) if revkire > 0 and iinet > 0 else 0

    lines = [
        "## Résultat IRPP 2023 (revenus 2023)",
        "",
        f"**Situation** : {params.situation.value}",
        f"**Impôt net** : {iinet:,.0f} €",
        f"**Nombre de parts** : {nbpt:.2f}",
        f"**Revenu net imposable** : {rni:,.0f} €",
        f"**Revenu fiscal de référence** : {revkire:,.0f} €",
    ]
    if txmoy > 0:
        lines.append(f"**Taux moyen effectif** : {txmoy:.1f} %")
    lines += [
        "",
        "*Calcul effectué avec le code source officiel DGFiP (sources2023m_8_0)*",
    ]
    return "\n".join(lines)


# ─── Serveur MCP ──────────────────────────────────────────────────────────────

mcp = FastMCP("irpp_mcp")

if not BINARY_PATH.exists():
    print(f"⚠️  Binaire irpp_calc introuvable : {BINARY_PATH}", file=sys.stderr)
    print("   Compilez-le depuis WSL : cd output && make", file=sys.stderr)


@mcp.tool(
    name="irpp_calculer_ir",
    output_schema=None,
    annotations={
        "title": "Calculer l'impôt sur le revenu 2023",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def irpp_calculer_ir(params: CalculerIRInput) -> str:
    """Calcule l'impôt sur le revenu français pour les revenus 2023 (déclaration 2024).

    Utilise le code source officiel DGFiP compilé via Mlang (INRIA). Calcul 100%
    local, aucune donnée envoyée à l'extérieur.

    Couvre : salaires, pensions/retraites, BNC régime normal, micro-foncier,
    dividendes, plus-values, quotient familial, PER, pension alimentaire.

    Args:
        params (CalculerIRInput): Paramètres fiscaux du foyer (formulaire 2042).

    Returns:
        str: Résultats en Markdown ou JSON selon response_format :
            - IINET  : impôt net final (après décote, réductions, crédits)
            - IRNET  : IR net avant crédits d'impôt
            - NBPT   : nombre de parts fiscales
            - RNI    : revenu net imposable
            - REVKIRE: revenu fiscal de référence
            - IAVIM  : impôt avant imputations
            - IRTOTAL: IR total foyer

    Examples:
        - Célibataire, 50 000 € de salaires → IINET ≈ 6 786 €
        - Marié, 2 enfants, 90 000 € → IINET ≈ 7 354 €, 3 parts
        - Retraité, 30 000 € de pension → IINET ≈ 1 637 €
    """
    stdin_data = _build_stdin(params.situation.value, params)
    results = await _run_binary(stdin_data)

    if params.response_format == ResponseFormat.json:
        return json.dumps(results, ensure_ascii=False, indent=2)

    return _format_markdown(results, params)


if __name__ == "__main__":
    mcp.run()
