"""
categorizer.py — Catégorisation automatique des transactions
=============================================================
Deux niveaux de catégorisation :
  1. Mapping utilisateur (appris via les corrections manuelles) → prioritaire
  2. Mapping par défaut (règles par mots-clés) → fallback

Le mapping utilisateur est stocké dans data/user_mapping.json.
Il s'enrichit à chaque correction manuelle via save_user_correction().

Catégories disponibles :
  Alimentation, Restaurants & Cafés, Transport, Shopping, Abonnements,
  Logement, Santé & Beauté, Loisirs & Culture, Voyages, Virements,
  Épargne & Investissement, Retraits, Revenus, Unknown
"""

import json
import os
import re

# Fichier de mapping appris par l'utilisateur
USER_MAPPING_FILE = os.path.join("data", "user_mapping.json")

# ─────────────────────────────────────────────
#  MAPPING PAR DÉFAUT (mots-clés → catégorie)
# ─────────────────────────────────────────────
# Structure : { "catégorie": ["mot-clé-1", "mot-clé-2", ...] }
# Les mots-clés sont comparés en lowercase et en correspondance partielle.

DEFAULT_MAPPING = {
    "Alimentation": [
        "leclerc", "carrefour", "lidl", "aldi", "monoprix", "franprix",
        "intermarche", "casino", "picard", "la fourche", "action",
        "grenier a pain", "patisserie", "boulangerie", "baguette",
        "asiamart", "douceurs trad", "chapanda"
    ],
    "Restaurants & Cafés": [
        "mae bowl", "five guys", "o tacos", "uber * eats", "uber *eats",
        "uber eats", "deliveroo", "mcdonald", "burger", "nyx*compassgroup",
        "api restauration", "yatai ramen", "thym et olive", "ivoire restos",
        "la brigade", "ab copains", "xft reaumur", "pret a manger",
        "pretamanger", "o crousti", "comptoir belge", "cotti coffee",
        "express coffee", "popotte", "sem tam cine"
    ],
    "Transport": [
        "sncf", "navigo", "ratp", "uber * pending", "ubr* pending",
        "taxi", "blablacar", "ouigo", "tgv", "transilien"
    ],
    "Shopping": [
        "amazon", "zara", "primark", "shein", "aliexpress", "asos",
        "zalando", "vinted", "c et a", "normal paris", "italie sport",
        "valthilde", "lucystyle", "adopt", "rituals", "notino",
        "iq concept", "italie seine", "westfield"
    ],
    "Abonnements": [
        "disney plus", "disney+", "spotify", "netflix", "apple.com",
        "amazon prime", "claude.ai", "google play", "sfr", "lycamobile",
        "uber *one", "basic fit", "bitstack"
    ],
    "Logement": [
        "bnppi residences", "residence servi", "loyer", "charges",
        "electricite", "engie", "edf", "gaz", "action logement"
    ],
    "Santé & Beauté": [
        "pharmacie", "medecin", "dentiste", "cardif", "mutuelle",
        "pointgyn", "washin"
    ],
    "Loisirs & Culture": [
        "cinema", "musee", "theatre", "fnac", "cultura", "q102"
    ],
    "Virements": [
        "vir inst", "vir sepa", "vir sct", "virement"
    ],
    "Revenus": [
        "salaire", "heineken entreprise", "mes extras", "caf", "apl",
        "action logement services"
    ],
    "Retraits": [
        "retrait dab", "retrait"
    ],
    "Épargne & Investissement": [
        "livret", "epargne", "assurance vie", "bitstack"
    ]
}

# Liste plate de toutes les catégories (pour l'interface de sélection)
ALL_CATEGORIES = sorted(DEFAULT_MAPPING.keys()) + ["Unknown"]


def load_user_mapping() -> dict:
    """
    Charge le mapping appris via les corrections manuelles.
    Retourne un dict vide si le fichier n'existe pas encore.

    Format du fichier :
        { "EXPRESS COFFEE": "Restaurants & Cafés", "SHEIN": "Shopping", ... }
    """
    if os.path.exists(USER_MAPPING_FILE):
        with open(USER_MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_user_correction(libelle: str, categorie: str):
    """
    Mémorise la correction d'une transaction pour les prochains imports.
    
    Principe : on extrait les mots significatifs du libellé (≥4 caractères)
    et on les associe à la catégorie choisie.

    Args:
        libelle:   Libellé brut de la transaction corrigée
        categorie: Catégorie choisie par l'utilisateur
    """
    user_mapping = load_user_mapping()
    
    # On stocke le libellé nettoyé comme clé (lowercase, sans caractères spéciaux)
    key = normalize_key(libelle)
    if key:
        user_mapping[key] = categorie

    os.makedirs("data", exist_ok=True)
    with open(USER_MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(user_mapping, f, ensure_ascii=False, indent=2)


def normalize_key(libelle: str) -> str:
    """Normalise un libellé pour en faire une clé de mapping stable."""
    return re.sub(r"[^a-z0-9 ]", "", libelle.lower()).strip()


def categorize_transaction(libelle: str, user_mapping: dict) -> str:
    """
    Catégorise une transaction selon deux niveaux :
      1. Mapping utilisateur (correspondance exacte ou partielle)
      2. Mapping par défaut (mots-clés)

    Args:
        libelle:      Libellé de la transaction (raw ou clean)
        user_mapping: Dict des corrections mémorisées par l'utilisateur

    Returns:
        Nom de la catégorie (str)
    """
    libelle_lower = libelle.lower()
    key = normalize_key(libelle)

    # ── Niveau 1 : Mapping utilisateur ──
    # Correspondance exacte d'abord
    if key in user_mapping:
        return user_mapping[key]

    # Correspondance partielle : on cherche si une clé connue est contenue dans le libellé
    for known_key, cat in user_mapping.items():
        if known_key and known_key in key:
            return cat

    # ── Niveau 2 : Mapping par défaut ──
    for categorie, keywords in DEFAULT_MAPPING.items():
        for kw in keywords:
            if kw.lower() in libelle_lower:
                return categorie

    return "Unknown"


def categorize_transactions(transactions: list[dict]) -> list[dict]:
    """
    Applique la catégorisation à toute une liste de transactions.
    Utilise le libellé_clean si disponible, sinon le libellé brut.

    Args:
        transactions: Liste de dicts transactions (format normalisé)

    Returns:
        La même liste avec le champ "categorie" rempli
    """
    user_mapping = load_user_mapping()

    for t in transactions:
        # On catégorise sur le libellé nettoyé pour de meilleurs résultats
        libelle_to_use = t.get("libelle_clean") or t.get("libelle", "")
        t["categorie"] = categorize_transaction(libelle_to_use, user_mapping)

    return transactions
