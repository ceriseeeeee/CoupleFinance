"""
parser_bnp.py — Parser BNP Paribas v2
=======================================
Utilise l'extraction texte ligne par ligne (comme parser_bourso)
car pdfplumber.extract_tables() échoue sur les PDFs BNP dont
les espaces sont encodés de façon non-standard.

Format des lignes BNP :
  "09.02 VIRSCTINSTEMIS/MOTIFTELE/BEN 07.02 255,00"
  "09.02 FACTURE(S)CARTE4974XXXXXXXX7956 10.02 3,68"

Particularités :
  - Dates au format DD.MM (sans l'année)
  - Libellés souvent collés (pas d'espaces)
  - Lignes multi-lignes (suite du libellé sans date)
  - Montants : "1032,92" ou "3,68" (pas de séparateur de milliers avec point)
"""

import pdfplumber
import re
import uuid
from collections import defaultdict
from datetime import datetime


# Lignes à ignorer
IGNORE_PATTERNS = [
    r"^RELEVE", r"^RELEVEDECOMPTE",
    r"^du\d", r"^du\s+\d",
    r"^SOTTEVILLE", r"^M JOSEPH",
    r"^RIB\s*:", r"^IBAN", r"^BIC\s*:",
    r"^Date\s+Nature", r"^SOLDE",
    r"^TOTAL DES", r"^BNP PARIBAS",
    r"^3477", r"^P\.\s*\d",
    r"^\d{9,}",  # Codes longs
    r"^Tél\.", r"^Service Client",
    r"^Les sommes", r"^Dépôts",
    r"^www\.",
    r"^Monnaie",
    r"^\*INTERETS",
    r"^\*COMMISSIONS",
    r"^Détail", r"^Utilisation",
    r"^Du \d",
    r"^Montant de votre",
    r"^Rappel",
    r"^Il vous",
    r"^Votre satisfaction",
    r"^606\d+",  # Codes internes BNP
    r"^SCPT",
    r"^Adressez",
    r"^Si vous",
]


def parse_bnp_pdf(filepath: str, personne: str) -> list[dict]:
    """
    Parse un relevé BNP Paribas PDF et retourne une liste de transactions.

    Stratégie par coordonnées (word-based) :
      Reconstruit les lignes à partir des mots et de leurs positions X/Y
      pour gérer les PDFs avec espaces non-encodés.
    """
    transactions = []
    annee = extract_year_from_bnp(filepath)

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                continue

            # Regroupement par ligne (même Y arrondi à 5px)
            line_map = defaultdict(list)
            for w in words:
                top_key = round(w["top"] / 5) * 5
                line_map[top_key].append(w)

            # Reconstruction des lignes avec espaces basés sur gap X
            raw_lines = []
            for top in sorted(line_map.keys()):
                wl = sorted(line_map[top], key=lambda w: w["x0"])
                if not wl:
                    continue
                reconstructed = wl[0]["text"]
                for i in range(1, len(wl)):
                    prev = wl[i-1]
                    curr = wl[i]
                    gap = curr["x0"] - prev["x1"]
                    if gap > 4:
                        reconstructed += " " + curr["text"]
                    else:
                        reconstructed += curr["text"]
                raw_lines.append(reconstructed.strip())

            # Fusion des lignes multi-lignes et parsing
            buffer = ""
            for line in raw_lines:
                if not line:
                    continue

                if should_ignore(line):
                    if buffer:
                        t = try_parse_bnp_line(buffer, personne, annee)
                        if t:
                            transactions.append(t)
                        buffer = ""
                    continue

                # Nouvelle transaction : commence par DD.MM
                if re.match(r"^\d{2}\.\d{2}\s", line):
                    if buffer:
                        t = try_parse_bnp_line(buffer, personne, annee)
                        if t:
                            transactions.append(t)
                    buffer = line
                else:
                    if buffer:
                        buffer = buffer + " " + line

            if buffer:
                t = try_parse_bnp_line(buffer, personne, annee)
                if t:
                    transactions.append(t)

    return transactions


def extract_year_from_bnp(filepath: str) -> int:
    """Extrait l'année depuis le contenu du relevé BNP."""
    try:
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""
            match = re.search(r"\b(20\d{2})\b", text)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return datetime.now().year


def should_ignore(line: str) -> bool:
    for pattern in IGNORE_PATTERNS:
        if re.match(pattern, line, re.IGNORECASE):
            return True
    return False


def try_parse_bnp_line(line: str, personne: str, annee: int) -> dict | None:
    """
    Tente de parser une ligne BNP reconstituée.

    Format : "DD.MM LIBELLE DD.MM MONTANT"
    Le montant est toujours en fin de ligne.
    """
    if not re.match(r"^\d{2}\.\d{2}", line):
        return None

    # Extraction du montant en fin de ligne
    montant_match = re.search(
        r"\s([\d]{1,3}(?:[\s.]?\d{3})*[,]\d{2})\s*$",
        line
    )
    if not montant_match:
        return None

    montant = parse_montant_bnp(montant_match.group(1))
    if montant is None or montant == 0:
        return None

    # Date opération : DD.MM au début
    date_str = line[:5]
    try:
        day, month = date_str.split(".")
        date = datetime(annee, int(month), int(day))
    except (ValueError, AttributeError):
        return None

    # Libellé : entre la date et le montant
    middle = line[5:montant_match.start()].strip()

    # Supprime la date valeur en fin de libellé (DD.MM ou DD/MM/YYYY)
    middle = re.sub(r"\s+\d{2}[\./]\d{2}(?:[\./]\d{4})?\s*$", "", middle).strip()

    if not middle:
        return None

    type_op = detect_type_bnp(middle)
    libelle_clean = clean_libelle_bnp(middle)

    return {
        "id": str(uuid.uuid4()),
        "date": date.strftime("%Y-%m-%d"),
        "mois": date.strftime("%Y-%m"),
        "libelle": middle,
        "libelle_clean": libelle_clean,
        "montant": montant,
        "type": type_op,
        "personne": personne,
        "banque": "BNP Paribas",
        "categorie": "Unknown",
        "corrige_manuellement": False
    }


def detect_type_bnp(libelle: str) -> str:
    """Détermine débit ou crédit depuis le libellé BNP."""
    l = libelle.upper()

    # Crédits
    if any(kw in l for kw in ["RECU", "RECU", "SALAIRE", "CAF", "ACTION LOGEMENT",
                                "MES EXTRAS", "ASSISTANCE", "WERO", "ENVOI D ARGENT"]):
        # Sauf si c'est un virement émis
        if "EMIS" in l:
            return "debit"
        return "credit"

    # Débits
    if any(kw in l for kw in ["FACTURE", "PRLV", "RETRAIT", "EMIS",
                                "COMMISSIONS", "INTERETS"]):
        return "debit"

    return "debit"  # Fallback


def parse_montant_bnp(montant_str: str) -> float | None:
    """Convertit un montant BNP en float. Format : "1032,92" ou "3,68"."""
    try:
        # Retire séparateurs de milliers (point ou espace)
        cleaned = re.sub(r"[.\s](?=\d{3}(?:[,]|$))", "", montant_str)
        cleaned = cleaned.replace(",", ".")
        return abs(float(cleaned))
    except (ValueError, AttributeError):
        return None


def clean_libelle_bnp(libelle: str) -> str:
    """
    Nettoie le libellé BNP verbeux.

    Cas principaux :
      "FACTURE(S)CARTE4974XXXXXXXX7956 DU090226 E.LECLERC" → "E.LECLERC"
      "DU090226 SPOTIFYFR"                                  → "SPOTIFYFR"
      "VIRSCTINSTEMIS/MOTIFTELE/BEN FAFOUMIOLADOUNNI"       → "VIR INST FAFOUMIOLADOUNNI"
      "PRLVSEPASFRECH/..."                                   → "PRLV SEPA SFR"
    """
    # Cas FACTURE(S) CARTE → extrait le marchand après DU DDMMYY
    facture = re.match(r"FACTURE\(S\)CARTE\S+\s+DU\d{6}\s+(.+?)(?:\s+[A-Z]{2,3}\s+[\d,\.]+EUR)?$",
                       libelle, re.IGNORECASE)
    if facture:
        return facture.group(1).strip()

    # Cas DU DDMMYY MARCHAND (sous-ligne BNP)
    du_match = re.match(r"DU\d{6}\s+(.+?)(?:\s+[A-Z]{2,3}\s+[\d,\.]+EUR)?$",
                        libelle, re.IGNORECASE)
    if du_match:
        return du_match.group(1).strip()

    # VIR* : supprime les refs techniques
    libelle = re.sub(r"/REFDO\s+\S+", "", libelle)
    libelle = re.sub(r"/REFBEN\s+\S+", "", libelle)
    libelle = re.sub(r"ECH/\S+", "", libelle)
    libelle = re.sub(r"IDEMETTEUR/\S+", "", libelle)
    libelle = re.sub(r"MDT/\S+", "", libelle)
    libelle = re.sub(r"REF/\S+", "", libelle)
    libelle = re.sub(r"LIB/\S+", "", libelle)
    libelle = re.sub(r"/MOTIF\s*", " ", libelle)
    libelle = re.sub(r"/BEN\s*", " → ", libelle)
    libelle = re.sub(r"/DE\s*", " DE ", libelle)

    # Supprime les hashes longs
    libelle = re.sub(r"\b[A-F0-9]{16,}\b", "", libelle)
    libelle = re.sub(r"\bNOTPROVIDED\b", "", libelle)

    # PRLV SEPA : garde le nom
    prlv = re.match(r"(PRLV\s*SEPA\s+\S+)", libelle, re.IGNORECASE)
    if prlv:
        return prlv.group(1).strip()

    return re.sub(r"\s+", " ", libelle).strip()
