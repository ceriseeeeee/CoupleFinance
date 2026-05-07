"""
parser_bnp.py — Parser pour les relevés BNP Paribas
====================================================
Extrait les transactions depuis un PDF BNP Paribas.

Format attendu (colonnes) :
  Date | Nature des opérations | Valeur | Débit | Crédit

Particularités BNP par rapport à BoursoBank :
  - Dates au format DD.MM (sans l'année — on la déduit du nom du fichier/contenu)
  - Libellés très verbeux, multi-lignes (refs, BEN, REFDO, etc.)
  - Lignes "FACTURE(S) CARTE" suivies de sous-lignes "DU XXXXXX MARCHAND"
  - Lignes de total et de solde à ignorer
  - Certaines transactions s'étalent sur plusieurs lignes dans le PDF
"""

import pdfplumber
import re
import uuid
from datetime import datetime


def parse_bnp_pdf(filepath: str, personne: str) -> list[dict]:
    """
    Parse un relevé BNP Paribas PDF et retourne une liste de transactions.

    Args:
        filepath: Chemin vers le PDF BNP Paribas
        personne: "Cerise" ou "Loïc"

    Returns:
        Liste de dicts de transactions normalisées (même format que parser_bourso)
    """
    transactions = []
    annee = extract_year_from_bnp(filepath)

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                # BNP : reconstruction des lignes multi-lignes
                rows = merge_multiline_rows(table)

                for row in rows:
                    row = [cell.strip() if cell else "" for cell in row]

                    # ── Filtres lignes non-transaction ──
                    if not row[0]:
                        continue
                    if not re.match(r"\d{2}\.\d{2}", row[0]):
                        continue  # Pas une date BNP (format DD.MM)
                    if any(kw in row[1].upper() for kw in [
                        "TOTAL DES OPERATIONS", "SOLDE", "MONTANT FRAIS",
                        "INTERETS DEBITEURS", "COMMISSIONS"
                    ]):
                        continue  # Lignes de bilan à ignorer

                    try:
                        date_str = row[0]       # "09.02"
                        libelle_raw = row[1]    # "VIR SEPA RECU /DE ..."
                        # row[2] = date valeur
                        debit_str = row[3]
                        credit_str = row[4]

                        # Reconstruction de la date complète avec l'année
                        date = parse_bnp_date(date_str, annee)

                        montant, type_op = parse_montant(debit_str, credit_str)
                        if montant is None:
                            continue

                        # Nettoyage du libellé verbeux BNP
                        libelle_clean = clean_libelle_bnp(libelle_raw)

                        transaction = {
                            "id": str(uuid.uuid4()),
                            "date": date.strftime("%Y-%m-%d"),
                            "mois": date.strftime("%Y-%m"),
                            "libelle": libelle_raw,
                            "libelle_clean": libelle_clean,
                            "montant": montant,
                            "type": type_op,
                            "personne": personne,
                            "banque": "BNP Paribas",
                            "categorie": "Unknown",
                            "corrige_manuellement": False
                        }
                        transactions.append(transaction)

                    except (IndexError, ValueError):
                        continue

    return transactions


def extract_year_from_bnp(filepath: str) -> int:
    """
    Extrait l'année depuis le contenu du relevé BNP.
    BNP n'inclut pas l'année dans les dates de transaction (ex: "09.02"),
    on la récupère depuis la ligne "du DD mois YYYY au DD mois YYYY".

    Fallback : année courante.
    """
    try:
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""
            # Cherche un pattern d'année sur 4 chiffres
            match = re.search(r"\b(20\d{2})\b", text)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return datetime.now().year


def parse_bnp_date(date_str: str, annee: int) -> datetime:
    """
    Convertit une date BNP "DD.MM" en datetime complet.

    Args:
        date_str: "09.02"
        annee:    2026

    Returns:
        datetime(2026, 2, 9)
    """
    day, month = date_str.split(".")
    return datetime(annee, int(month), int(day))


def merge_multiline_rows(table: list) -> list:
    """
    BNP Paribas produit souvent des lignes multi-lignes dans ses PDFs :
    la première ligne a la date et le début du libellé,
    les lignes suivantes ont le reste du libellé mais pas de date.

    Cette fonction fusionne ces fragments en une seule ligne logique.

    Exemple avant :
        ["09.02", "VIR SEPA RECU /DE MME OLADOUNNI FAFOUMI", "", "", "350,00"]
        ["",      "/MOTIF VIREMENT DE MLLE FAFOUMI",          "", "", ""]
    
    Exemple après :
        ["09.02", "VIR SEPA RECU /DE MME OLADOUNNI FAFOUMI /MOTIF VIREMENT DE MLLE FAFOUMI", "", "", "350,00"]
    """
    merged = []
    current = None

    for row in table:
        if not row:
            continue

        # Normalisation : remplace None par ""
        row = [cell.strip() if cell else "" for cell in row]

        # Si la ligne commence par une date DD.MM → nouvelle transaction
        if row[0] and re.match(r"\d{2}\.\d{2}", row[0]):
            if current:
                merged.append(current)
            current = list(row)
        else:
            # Continuation d'une transaction précédente → fusion du libellé
            if current and row[1]:
                current[1] = (current[1] + " " + row[1]).strip()

    if current:
        merged.append(current)

    return merged


def parse_montant(debit_str: str, credit_str: str) -> tuple:
    """Même logique que parser_bourso — convertit débit/crédit en montant + type."""
    def clean(s: str):
        s = s.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
        if not s:
            return None
        try:
            return abs(float(s))
        except ValueError:
            return None

    debit = clean(debit_str)
    credit = clean(credit_str)

    if debit:
        return debit, "debit"
    elif credit:
        return credit, "credit"
    return None, None


def clean_libelle_bnp(libelle: str) -> str:
    """
    Simplifie le libellé très verbeux BNP pour l'affichage et la catégorisation.

    BNP inclut des blocs de référence comme :
        "/MOTIF ...", "/BEN ...", "/REFDO ...", "/REFBEN ...", "ECH/...", "MDT/...", "REF/..."

    Exemples :
        "VIR SCT INST EMIS /MOTIF TELE /BEN FAFOUMI OLADOUNNI /REFDO 4F682..."
        → "VIR SCT INST EMIS TELE FAFOUMI OLADOUNNI"

        "PRLV SEPA BNPPI RESIDENCES SERVICES ECH/090226 ID EMETTEUR/FR49ZZZ..."
        → "PRLV SEPA BNPPI RESIDENCES SERVICES"

        "FACTURE(S) CARTE 4974XXXXXXXX7956 DU 090226 E.LECLERC FRA 3,68EUR"
        → "E.LECLERC"
    """
    # Cas spécial : FACTURE(S) CARTE → on extrait juste le nom du marchand
    # Format : "FACTURE(S) CARTE XXXXXXXX DU DDMMYY MARCHAND"
    # ou sous-ligne : "DU DDMMYY MARCHAND"
    facture_match = re.search(r"DU\s+\d{6}\s+(.+?)(?:\s+[A-Z]{2,3}\s+[\d,\.]+EUR)?$", libelle)
    if facture_match:
        marchand = factura_match.group(1) if (factura_match := facture_match) else ""
        # Supprime les suffixes monétaires résiduels
        marchand = re.sub(r"\s+[A-Z]{2,3}\s+[\d,\.]+EUR.*$", "", marchand)
        return marchand.strip()

    # Supprime les blocs de référence techniques
    libelle = re.sub(r"/REFDO\s+\S+", "", libelle)
    libelle = re.sub(r"/REFBEN\s+\S+", "", libelle)
    libelle = re.sub(r"ECH/\S+", "", libelle)
    libelle = re.sub(r"ID\s+EMETTEUR/\S+", "", libelle)
    libelle = re.sub(r"MDT/\S+", "", libelle)
    libelle = re.sub(r"REF/\S+", "", libelle)
    libelle = re.sub(r"LIB/\S+", "", libelle)

    # Simplifie "/MOTIF XXXX /BEN YYYY" → garde le motif et le bénéficiaire
    libelle = re.sub(r"/MOTIF\s+", " ", libelle)
    libelle = re.sub(r"/BEN\s+", " → ", libelle)
    libelle = re.sub(r"/DE\s+", " DE ", libelle)

    # Supprime les codes alphanumériques longs (hashes de référence)
    libelle = re.sub(r"\b[A-F0-9]{16,}\b", "", libelle)

    # Nettoyage final des espaces multiples
    libelle = re.sub(r"\s+", " ", libelle).strip()

    return libelle
