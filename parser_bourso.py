"""
parser_bourso.py — Parser pour les relevés BoursoBank
======================================================
Extrait les transactions depuis un PDF BoursoBank.

STRATÉGIE : extraction par texte brut (pas par tableau)
-------------------------------------------------------
pdfplumber.extract_tables() échoue sur certains relevés Bourso car :
  - Certaines lignes sont multi-lignes (PayPal, PRLV SEPA avec références)
  - La détection automatique de tableau rate les bordures

On parse donc le texte ligne par ligne avec regex,
ce qui est plus robuste et fonctionne sur tous les formats Bourso.

Format des lignes à capturer :
  "01/12/2025 CARTE 28/11/25 BERSHKA 4 CB*1301 01/12/2025 62,72"
  "01/12/2025 VIR INST M JOSEPH SHARON OUASSA 30/11/2025 775,00"
"""

import pdfplumber
import re
from datetime import datetime
from utils import make_transaction_id


# Patterns de lignes à ignorer (en-têtes, pieds de page, lignes de bilan)
IGNORE_PATTERNS = [
    r"^SOLDE AU",
    r"^Nouveau solde",
    r"^Montant frais",
    r"^Date\s+op",
    r"^Libellé",
    r"^Valeur\s+D",
    r"^B\.I\.C\.",
    r"^Boursorama",
    r"^Service Client",
    r"^Adresse du",
    r"^A réception",
    r"^A défaut",
    r"^\* Montant",
    r"^44 rue",
    r"^Mod\.",
    r"^Banque\s+Guichet",
    r"^Date\s+N°",
    r"^\d{2}/\d{2}/\d{4}\s+\d{5}",  # Ligne d'en-tête avec numéros de compte
]


def parse_bourso_pdf(filepath: str, personne: str) -> list[dict]:
    """
    Parse un relevé BoursoBank PDF et retourne une liste de transactions.

    Stratégie par coordonnées (word-based) :
      Certains PDFs Bourso ont des espaces encodés de façon non-standard,
      ce qui fait que pdfplumber colle les mots. On contourne en :
      1. Extrayant chaque mot avec sa position Y (coordonnée top)
      2. Regroupant les mots par ligne (même Y ± 5px)
      3. Reconstruisant les lignes avec des espaces entre mots
      4. Fusionnant les lignes multi-lignes (PayPal, PRLV SEPA...)

    Args:
        filepath: Chemin vers le PDF BoursoBank
        personne: "Cerise" ou "Loïc"

    Returns:
        Liste de dicts transactions normalisées
    """
    from collections import defaultdict
    transactions = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:

            # ── Extraction des mots avec coordonnées ──
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                continue

            # ── Regroupement par ligne (même position Y arrondie à 5px) ──
            line_map = defaultdict(list)
            for w in words:
                top_key = round(w["top"] / 5) * 5
                line_map[top_key].append(w)

            # ── Reconstruction des lignes (mots triés par X) ──
            raw_lines = []
            for top in sorted(line_map.keys()):
                words_in_line = sorted(line_map[top], key=lambda w: w["x0"])
                line_text = " ".join(w["text"] for w in words_in_line)
                raw_lines.append(line_text)

            # ── Fusion des lignes multi-lignes et parsing ──
            buffer = ""
            for line in raw_lines:
                line = line.strip()
                if not line:
                    continue

                if should_ignore(line):
                    if buffer:
                        t = try_parse_line(buffer, personne)
                        if t:
                            transactions.append(t)
                        buffer = ""
                    continue

                # Nouvelle transaction : commence par DD/MM/YYYY
                if re.match(r"^\d{2}/\d{2}/\d{4}\s", line):
                    if buffer:
                        t = try_parse_line(buffer, personne)
                        if t:
                            transactions.append(t)
                    buffer = line
                else:
                    # Continuation multi-lignes (refs PayPal, etc.)
                    if buffer:
                        buffer = buffer + " " + line

            # Flush final
            if buffer:
                t = try_parse_line(buffer, personne)
                if t:
                    transactions.append(t)

    return transactions


def should_ignore(line: str) -> bool:
    """Retourne True si la ligne est un en-tête, pied de page ou ligne de bilan."""
    for pattern in IGNORE_PATTERNS:
        if re.match(pattern, line, re.IGNORECASE):
            return True
    return False


def try_parse_line(line: str, personne: str) -> dict | None:
    """
    Tente de parser une ligne (potentiellement multi-lignes reconstituée).

    Structure d'une ligne Bourso reconstituée :
      "DD/MM/YYYY LIBELLÉ [DD/MM/YYYY] MONTANT"

    Le montant est toujours en fin de ligne.
    La date valeur (deuxième date) est optionnelle selon les lignes.

    Retourne None si la ligne n'est pas parseable comme transaction.
    """
    if not re.match(r"^\d{2}/\d{2}/\d{4}", line):
        return None

    # ── Extraction du montant (toujours en fin de ligne) ──
    # Format Bourso : "1.115,55" ou "62,72" ou "1 115,55"
    montant_match = re.search(
        r"\s([\d]{1,3}(?:[.\s]?\d{3})*,\d{2})\s*$",
        line
    )
    if not montant_match:
        return None

    montant = parse_montant_bourso(montant_match.group(1))
    if montant is None or montant == 0:
        return None

    # ── Extraction de la date opération ──
    date_str = line[:10]
    try:
        date = datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        return None

    # ── Extraction du libellé ──
    # Ce qui se trouve entre la date_op et le montant
    middle = line[10:montant_match.start()].strip()

    # Supprime la date valeur en fin de libellé si présente ("DD/MM/YYYY")
    middle = re.sub(r"\s+\d{2}/\d{2}/\d{4}\s*$", "", middle).strip()

    if not middle:
        return None

    # ── Détection débit/crédit ──
    type_op = detect_type(middle)
    libelle_clean = clean_libelle_bourso(middle)

    return {
        "id": make_transaction_id(date.strftime("%Y-%m-%d"), libelle_clean, montant, personne, "BoursoBank"),
        "date": date.strftime("%Y-%m-%d"),
        "mois": date.strftime("%Y-%m"),
        "libelle": middle,
        "libelle_clean": libelle_clean,
        "montant": montant,
        "type": type_op,
        "personne": personne,
        "banque": "BoursoBank",
        "categorie": "Unknown",
        "corrige_manuellement": False
    }


def detect_type(libelle: str) -> str:
    """
    Détermine si la transaction est un débit ou un crédit.

    Bourso ne met pas de signe — on déduit du libellé :
      Crédits : VIR reçu, AVOIR (remboursement)
      Débits  : CARTE, PRLV, RETRAIT, VIR émis, TDF
    """
    l = libelle.upper()

    # Crédits explicites
    if "AVOIR" in l:
        return "credit"
    if "VIREMENT DEPUIS" in l:
        return "credit"

    # VIR : crédit si reçu, débit si émis
    if "VIR" in l:
        if any(kw in l for kw in ["EMIS", "SCT INST EMIS"]):
            return "debit"
        return "credit"  # VIR sans EMIS = reçu par défaut

    # Débits explicites
    if any(kw in l for kw in ["CARTE", "PRLV", "RETRAIT", "TDF"]):
        return "debit"

    return "debit"  # Fallback


def parse_montant_bourso(montant_str: str) -> float | None:
    """
    Convertit un montant format français Bourso en float.

    Exemples :
      "62,72"    → 62.72
      "1.115,55" → 1115.55
      "1 115,55" → 1115.55
    """
    try:
        # Retire les séparateurs de milliers (point ou espace)
        cleaned = re.sub(r"[.\s](?=\d{3})", "", montant_str)
        # Virgule décimale → point
        cleaned = cleaned.replace(",", ".")
        return abs(float(cleaned))
    except (ValueError, AttributeError):
        return None


def clean_libelle_bourso(libelle: str) -> str:
    """
    Simplifie et corrige le libellé Bourso pour l'affichage et la catégorisation.

    Problème connu : certains PDFs Bourso encodent les polices sans espaces,
    ce qui donne "VIRINSTMJOSEPHSHARONOUASSA" au lieu de "VIR INST M JOSEPH SHARON OUASSA".
    On ré-injecte les espaces sur les prefixes connus puis on nettoie le reste.

    Transformations :
      "CARTE28/11/25BERSHKA4TEMPS4CB*1301"  → "BERSHKA 4 TEMPS 4"
      "CARTE29/11/25notino.frCB*1301"       → "notino.fr"
      "VIRINSTMJOSEPHSHARONOUASSA"          → "VIR INST M JOSEPH SHARON OUASSA"
      "VIRINSTMMEOLADOUNNIFAFOUMI"          → "VIR INST MME OLADOUNNI FAFOUMI"
      "PRLVSEPAP ayPalEurope..."            → "PRLV SEPA PayPal Europe"
      "RETRAITDAB11/12/25GARESNCF"         → "RETRAIT DAB GARE SNCF"
    """
    # ── Étape 1 : ré-injecter les espaces sur les préfixes connus (collés) ──
    prefixes_colles = [
        ("CARTEAVOIR", "CARTE AVOIR"),   # Cas improbable mais sécurité
        ("CARTERETRAIT", "CARTE RETRAIT"),
        ("VIRINSTMME", "VIR INST MME"),
        ("VIRINSTM ", "VIR INST M "),
        ("VIRINST", "VIR INST"),
        ("VIRSEPA", "VIR SEPA"),
        ("PRLVSEPA", "PRLV SEPA"),
        ("RETRAITDAB", "RETRAIT DAB"),
        ("AVOIRSEPA", "AVOIR SEPA"),
    ]
    for collé, espacé in prefixes_colles:
        if libelle.upper().startswith(collé.replace(" ", "")):
            libelle = espacé + libelle[len(collé.replace(" ", "")):]
            break

    # ── Étape 2 : supprime préfixe "CARTE DD/MM/YY " ou "AVOIR DD/MM/YY " ──
    libelle = re.sub(r"^(CARTE|AVOIR)\s*\d{2}/\d{2}/\d{2}\s*", "", libelle, flags=re.IGNORECASE)

    # ── Étape 3 : supprime suffixe " CB*XXXX" ──
    libelle = re.sub(r"\s*CB\*\d+\s*$", "", libelle)

    # ── Étape 4 : PRLV SEPA → garde nom jusqu'aux références numériques ──
    if libelle.upper().startswith("PRLV SEPA"):
        match = re.match(r"(PRLV SEPA\s+.+?)(?:\s+\d{7,}|\s+RUM\s+|\s+ECH/|$)", libelle, re.IGNORECASE)
        if match:
            libelle = match.group(1).strip()

    # ── Étape 5 : RETRAIT DAB → supprime la date intercalée ──
    libelle = re.sub(r"^(RETRAIT DAB)\s*\d{2}/\d{2}/\d{2}\s*", r"\1 ", libelle, flags=re.IGNORECASE)

    return libelle.strip()
