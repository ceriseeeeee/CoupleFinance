"""
parser_csv.py — Parsers CSV pour BoursoBank, BNP Paribas et Trade Republic
============================================================================
Beaucoup plus fiables que les parsers PDF car le format CSV est propre.

Détection automatique du format selon les colonnes du fichier.
"""

import csv
import uuid
import re
from datetime import datetime
from io import StringIO


def detect_csv_bank(content: str) -> str:
    """
    Détecte la banque depuis les en-têtes du CSV.
    Retourne 'bourso', 'bnp', 'traderepublic' ou 'unknown'.
    """
    first_line = content.split('\n')[0].lower()

    if 'dateop' in first_line or 'accountlabel' in first_line:
        return 'bourso'
    elif 'compte de ch' in first_line or ('paiement' in content[:200].lower() and ';' in first_line):
        return 'bnp'
    elif 'datetime' in first_line and 'asset_class' in first_line:
        return 'traderepublic'

    return 'unknown'


def parse_csv(filepath: str, personne: str) -> list[dict]:
    """
    Parse un fichier CSV et retourne les transactions.
    Détecte automatiquement le format.
    """
    # Lecture avec détection d'encodage
    for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    banque = detect_csv_bank(content)

    if banque == 'bourso':
        return parse_bourso_csv(content, personne)
    elif banque == 'bnp':
        return parse_bnp_csv(content, personne)
    elif banque == 'traderepublic':
        return parse_traderepublic_csv(content, personne)
    else:
        return []


# ─────────────────────────────────────────────
#  PARSER BOURSOBANK CSV
# ─────────────────────────────────────────────

def parse_bourso_csv(content: str, personne: str) -> list[dict]:
    """
    Parse le CSV BoursoBank.

    Format des colonnes :
      dateOp ; dateVal ; label ; category ; categoryParent ;
      supplierFound ; amount ; comment ; accountNum ; accountLabel ; accountbalance

    Le label est : "Nom Marchand | CARTE DD/MM/YY LIBELLE CB*1301"
    ou juste : "VIR INST MME OLADOUNNI FAFOUMI | VIR INST MME OLADOUNNI FAFOUMI"
    """
    transactions = []
    reader = csv.DictReader(StringIO(content), delimiter=';')

    for row in reader:
        try:
            # Date
            date_str = row.get('dateOp', '').strip()
            date = datetime.strptime(date_str, '%Y-%m-%d')

            # Montant
            amount_str = row.get('amount', '').strip().replace(',', '.')
            if not amount_str:
                continue
            montant = float(amount_str)
            type_op = 'credit' if montant > 0 else 'debit'
            montant = abs(montant)

            # Libellé — on prend la partie après le "|" si présente (libellé brut)
            label_full = row.get('label', '').strip()
            if '|' in label_full:
                parts = label_full.split('|')
                nom_marchand = parts[0].strip()    # "Notino"
                libelle_brut = parts[1].strip()    # "CARTE 29/04/26 notino.fr CB*1301"
            else:
                nom_marchand = label_full
                libelle_brut = label_full

            # Libellé clean : on préfère le nom marchand fourni par Bourso
            libelle_clean = nom_marchand if nom_marchand else clean_libelle_bourso_csv(libelle_brut)

            transactions.append({
                "id": str(uuid.uuid4()),
                "date": date.strftime("%Y-%m-%d"),
                "mois": date.strftime("%Y-%m"),
                "libelle": libelle_brut,
                "libelle_clean": libelle_clean,
                "montant": round(montant, 2),
                "type": type_op,
                "personne": personne,
                "banque": "BoursoBank",
                "categorie": "Unknown",
                "corrige_manuellement": False
            })

        except (ValueError, KeyError):
            continue

    return transactions


def clean_libelle_bourso_csv(libelle: str) -> str:
    """Nettoie un libellé brut Bourso."""
    libelle = re.sub(r'^(CARTE|AVOIR)\s+\d{2}/\d{2}/\d{2}\s+', '', libelle)
    libelle = re.sub(r'\s+CB\*\d+\s*$', '', libelle)
    return libelle.strip()


# ─────────────────────────────────────────────
#  PARSER BNP PARIBAS CSV
# ─────────────────────────────────────────────

def parse_bnp_csv(content: str, personne: str) -> list[dict]:
    """
    Parse le CSV BNP Paribas.

    Format des colonnes (séparateur ;, pas d'en-tête standard) :
      date ; type_court ; type_long ; libellé_complet ; montant

    Première ligne = infos du compte (à ignorer).
    """
    transactions = []
    lines = content.strip().split('\n')

    for i, line in enumerate(lines):
        # Ignore la première ligne (infos compte)
        if i == 0:
            continue

        # Parse la ligne CSV
        try:
            parts = list(csv.reader([line], delimiter=';'))[0]
            if len(parts) < 5:
                continue

            date_str  = parts[0].strip()
            type_op   = parts[1].strip()
            libelle   = parts[3].strip()
            montant_str = parts[4].strip().replace(',', '.')

            # Date DD/MM/YYYY
            date = datetime.strptime(date_str, '%d/%m/%Y')

            # Montant
            montant = float(montant_str)
            op_type = 'credit' if montant > 0 else 'debit'
            montant = abs(montant)

            # Libellé clean
            libelle_clean = clean_libelle_bnp_csv(libelle)

            transactions.append({
                "id": str(uuid.uuid4()),
                "date": date.strftime("%Y-%m-%d"),
                "mois": date.strftime("%Y-%m"),
                "libelle": libelle,
                "libelle_clean": libelle_clean,
                "montant": round(montant, 2),
                "type": op_type,
                "personne": personne,
                "banque": "BNP Paribas",
                "categorie": "Unknown",
                "corrige_manuellement": False
            })

        except (ValueError, IndexError):
            continue

    return transactions


def clean_libelle_bnp_csv(libelle: str) -> str:
    """
    Nettoie un libellé BNP CSV.

    Exemples :
      "FACTURE CARTE DU 010126 NEWREST WAGONS- CARTE 4974XXXXXXXX7956 FRA 20,05EUR"
      → "NEWREST WAGONS"
      "VIR SEPA RECU /DE ACTION LOGEMENT SERVICES PP /MOTIF ..."
      → "ACTION LOGEMENT SERVICES"
      "PRLV SEPA SFR ECH/050126 ..."
      → "SFR"
    """
    # FACTURE CARTE DU DDMMYY MARCHAND
    facture = re.match(
        r"FACTURE\s+CARTE\s+DU\s+\d{6}\s+(.+?)(?:\s+CARTE\s+\d{4}|\s+[A-Z]{3}\s+[\d,]+EUR|$)",
        libelle, re.IGNORECASE
    )
    if facture:
        return facture.group(1).strip()

    # VIR SEPA RECU /DE XXX /MOTIF
    vir_recu = re.match(r"VIR\s+\w+\s+RECU\s+/DE\s+(.+?)(?:\s+/MOTIF|\s+/REF|$)", libelle, re.IGNORECASE)
    if vir_recu:
        return vir_recu.group(1).strip()

    # VIR * EMIS /MOTIF XXX /BEN YYY
    vir_emis = re.match(r"VIR\s+\w+\s+EMIS\s+/MOTIF\s+(.+?)(?:\s+/BEN|\s+/REFDO|$)", libelle, re.IGNORECASE)
    if vir_emis:
        return vir_emis.group(1).strip()

    # PRLV SEPA NOM ECH/...
    prlv = re.match(r"PRLV\s+SEPA\s+(.+?)(?:\s+ECH/|\s+ID\s+EMETTEUR|$)", libelle, re.IGNORECASE)
    if prlv:
        return prlv.group(1).strip()

    # Supprime les références techniques
    libelle = re.sub(r'/REFDO\s+\S+', '', libelle)
    libelle = re.sub(r'/REFBEN\s+\S+', '', libelle)
    libelle = re.sub(r'ECH/\S+', '', libelle)
    libelle = re.sub(r'ID\s+EMETTEUR/\S+', '', libelle)
    libelle = re.sub(r'MDT/\S+', '', libelle)
    libelle = re.sub(r'REF/\S+', '', libelle)
    libelle = re.sub(r'\b[A-F0-9]{16,}\b', '', libelle)

    return re.sub(r'\s+', ' ', libelle).strip()


# ─────────────────────────────────────────────
#  PARSER TRADE REPUBLIC CSV
# ─────────────────────────────────────────────

def parse_traderepublic_csv(content: str, personne: str) -> list[dict]:
    """
    Parse le CSV Trade Republic.

    Colonnes utiles :
      date ; account_type ; type ; name ; amount ; description

    On ignore les transactions TRADING (crypto/actions) sauf si demandé.
    On garde : CARD_TRANSACTION, TRANSFER_*, PAYMENT_*
    """
    transactions = []
    reader = csv.DictReader(StringIO(content), delimiter=',')

    for row in reader:
        try:
            # Date
            date_str = row.get('date', '').strip()
            date = datetime.strptime(date_str, '%Y-%m-%d')

            # Montant
            amount_str = row.get('amount', '').strip()
            if not amount_str:
                continue
            montant = float(amount_str)

            # Ignore les transactions à 0
            if montant == 0:
                continue

            type_op = 'credit' if montant > 0 else 'debit'
            montant = abs(montant)

            # Type de transaction TR
            tr_type = row.get('type', '').strip()

            # On ignore les achats/ventes de titres (TRADING)
            if tr_type in ('BUY', 'SELL', 'DIVIDEND', 'PEA_MARKETING'):
                continue

            # Libellé
            name = row.get('name', '').strip()
            description = row.get('description', '').strip()
            libelle = name if name else description
            libelle_clean = clean_libelle_tr(libelle, description, tr_type)

            transactions.append({
                "id": str(uuid.uuid4()),
                "date": date.strftime("%Y-%m-%d"),
                "mois": date.strftime("%Y-%m"),
                "libelle": description or libelle,
                "libelle_clean": libelle_clean,
                "montant": round(montant, 2),
                "type": type_op,
                "personne": personne,
                "banque": "Trade Republic",
                "categorie": "Unknown",
                "corrige_manuellement": False
            })

        except (ValueError, KeyError):
            continue

    return transactions


def clean_libelle_tr(name: str, description: str, tr_type: str) -> str:
    """Nettoie un libellé Trade Republic."""
    # Pour les virements reçus, extrait le nom de l'émetteur
    if 'INBOUND' in tr_type or 'INCOMING' in tr_type:
        match = re.search(r'from\s+(.+?)(?:\s+\(|$)', description, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Supprime les numéros de référence en fin de nom
    name = re.sub(r'\s+\d{7,}$', '', name)
    name = re.sub(r'null$', '', name).strip()

    return name if name else description
