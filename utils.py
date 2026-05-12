import hashlib
import re


def make_transaction_id(date, libelle, montant, personne, banque):
    raw = f"{date}|{libelle}|{montant:.2f}|{personne}|{banque}"
    raw = re.sub(r"\s+", " ", raw.lower()).strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
