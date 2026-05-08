"""
categorizer.py — Catégorisation automatique v4
===============================================
Trois niveaux de catégorisation :
  1. Mapping utilisateur (corrections manuelles mémorisées) → prioritaire
  2. Mapping par mots-clés enrichis (500+ marchands français) → rapide
  3. IA Claude API → fallback pour les Unknown restants

Le mapping utilisateur est stocké dans data/user_mapping.json.
"""

import json
import os
import re
import requests

USER_MAPPING_FILE = os.path.join("data", "user_mapping.json")

# ─────────────────────────────────────────────
#  MAPPING PAR DÉFAUT — enrichi 500+ marchands
# ─────────────────────────────────────────────

DEFAULT_MAPPING = {
    "Alimentation": [
        # Supermarchés
        "leclerc", "carrefour", "lidl", "aldi", "monoprix", "franprix",
        "intermarche", "casino", "picard", "la fourche", "biocoop",
        "naturalia", "grand frais", "simply market", "super u", "hyper u",
        "market", "auchan", "cora", "match", "netto", "leader price",
        "g20", "8 a huit", "proxi", "vival", "spar", "sherpa",
        # Boulangeries / pâtisseries
        "grenier a pain", "patisserie", "boulangerie", "baguette", "brioche",
        "paul ", "eric kayser", "maison landemaine", "poilane", "gontran cherrier",
        "m.a. vanille", "les gourmandises", "comptoir belge", "o crousti",
        "patisserie bou", "croust", "crousti",
        # Épiceries / traiteurs
        "asiamart", "douceurs trad", "chapanda", "ivoire restos",
        "epicerie", "traiteur", "primeur", "marche", "fourche distri",
        "la fourche", "alatone", "dolaka",
    ],

    "Restaurants & Cafés": [
        # Fast food
        "mcdonald", "mcdo", "burger king", "kfc", "subway", "five guys",
        "o tacos", "tacos", "kebab", "pizza hut", "dominos", "pizza",
        "sushi", "poke", "bowl", "wrap",
        # Livraison
        "uber * eats", "uber *eats", "ubereats", "deliveroo", "just eat",
        "uber eats", "uber  eats",
        # Cafés / snacks
        "nyx*compassgroup", "nyx*compass", "compassgroup", "compass group",
        "api restauration", "residence servi", "express coffee", "coffee",
        "starbucks", "cotti coffee", "momen tea", "bubble tea",
        "grenier a pain", "cotti",
        # Restaurants
        "mae bowl", "yatai ramen", "ramen", "thym et olive", "pepperico",
        "indiana", "veng hour", "lili food", "bolkiri", "degray",
        "sunday*le paradis", "la brigade", "ab copains", "xft reaumur",
        "pretamanger", "pret a manger", "italie sport", "sem tam cine",
        "somasando", "sama ", "roll in", "wesley chatel", "tenz",
        "full plate", "french s style", "l auberge", "popotte",
        "dmc ", "q102", "auberge", "bonne baguette",
    ],

    "Transport": [
        "sncf", "navigo", "ratp", "service navigo", "transilien",
        "uber * pending", "ubr* pending", "uber pending",
        "taxi", "blablacar", "ouigo", "tgv", "intercites",
        "autoroutes", "vinci autoroutes", "sanef", "area",
        "parking", "velib", "lime", "bird", "tier",
        "air france", "easyjet", "ryanair", "transavia", "volotea",
        "sncf-voyageurs", "oui.sncf", "thalys", "eurostar",
        "aeroport", "navette", "bus", "metro",
        "italie seine", "autoroutes du s",
    ],

    "Shopping": [
        # Mode
        "zara", "zara.com", "primark", "shein", "eur.shein", "aliexpress",
        "asos", "zalando", "vinted", "c et a", "h m hennes", "h&m",
        "bershka", "bershka.com", "pull and bear", "stradivarius",
        "mango", "uniqlo", "cos ", "arket", "monki",
        "hm ", "new look", "promod", "kiabi", "la halle",
        # Maison / déco
        "ikea", "maisons du monde", "but ", "conforama",
        "leroy merlin", "castorama", "bricorama",
        # Parfumerie / beauté (hors soins)
        "sephora", "marionnaud", "nocibe", "adopt", "yves rocher",
        "rituals", "notino", "notino.fr", "sc-lucystyle", "lucystyle",
        "valthilde", "phie benamran",
        # Divers shopping
        "normal paris", "normal ", "action ", "gifi", "tati",
        "amazon", "amazon payments", "fnac", "darty", "boulanger",
        "apple store", "samsung", "fnac.com",
        "les quatre temps", "westfield", "italie sport",
        "mgp*vinted", "vinted", "iq concept", "sc-bonne",
        "2a retail", "alatone", "dolaka internatio",
        "phie ", "benamran", "sc-",
    ],

    "Abonnements": [
        "disney plus", "disney+", "spotify", "netflix", "amazon prime",
        "claude.ai", "google play", "apple.com", "apple.com/bill",
        "uber *one", "uber one", "deezer", "canal+", "canal plus",
        "youtube premium", "twitch", "adobe", "microsoft",
        "office 365", "icloud", "dropbox", "notion",
        "sfr", "orange", "bouygues", "free mobile", "lycamobile",
        "basic fit", "keepcool", "fitness park", "moving",
        "bitstack", "bitstack sas",
    ],

    "Logement": [
        "bnppi residences", "residence servi 4", "loyer",
        "charges", "electricite", "edf", "engie", "gaz",
        "eau ", "veolia", "suez",
        "action logement", "caf ", "apl ",
        "assurance", "cardif", "macif", "maaf", "axa",
        "taxe fonciere", "taxe habitation",
        "washin", "laundry", "laverie",
    ],

    "Santé & Beauté": [
        "pharmacie", "medecin", "docteur", "dentiste", "opticien",
        "mutuelle", "secu", "cpam", "ameli",
        "cardif iard", "pointgyn", "gyneco",
        "laboratoire", "analyse", "radio", "scanner",
        "kiné", "kinesitherapie", "osteo",
        "yves rocher", "rituals", "notino",
    ],

    "Loisirs & Culture": [
        "cinema", "ugc", "mk2", "pathe", "gaumont",
        "musee", "theatre", "concert", "spectacle",
        "fnac", "cultura", "gibert", "librairie",
        "jeux video", "steam", "playstation", "xbox",
        "bowling", "karting", "laser game", "escape game",
        "noel la villette", "sumup *loisirs", "loisirs",
        "parc", "zoo", "aquarium", "disneyland",
        "koepfers", "steinbuc",
    ],

    "Voyages": [
        "hotel", "airbnb", "booking", "expedia",
        "hostel", "gite", "camping",
        "autoroutes", "peage", "vinci",
        "travel", "voyage", "vacances",
        "italie sport", "location voiture",
        "aeroport", "bagages",
    ],

    "Virements": [
        "vir inst", "vir sepa", "vir sct",
        "virement depuis boursobank",
        "wero ",
    ],

    "Revenus": [
        "salaire", "heineken entreprise", "mes extras",
        "caf des", "apl", "action logement services",
        "vir sepa recu", "vir sct inst recu",
        "remboursement", "avoir ",
    ],

    "Retraits": [
        "retrait dab", "retrait ",
    ],

    "Épargne & Investissement": [
        "livret", "epargne", "assurance vie",
        "bitstack", "bitstack sas",
        "bourse", "investissement", "placement",
        "pea ", "per ",
    ],
}

ALL_CATEGORIES = sorted(DEFAULT_MAPPING.keys()) + ["Unknown"]


# ─────────────────────────────────────────────
#  MAPPING UTILISATEUR
# ─────────────────────────────────────────────

def load_user_mapping() -> dict:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(USER_MAPPING_FILE):
        with open(USER_MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_user_correction(libelle: str, categorie: str):
    """Mémorise une correction manuelle."""
    user_mapping = load_user_mapping()
    key = normalize_key(libelle)
    if key:
        user_mapping[key] = categorie
    os.makedirs("data", exist_ok=True)
    with open(USER_MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(user_mapping, f, ensure_ascii=False, indent=2)


def normalize_key(libelle: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", libelle.lower()).strip()


# ─────────────────────────────────────────────
#  CATÉGORISATION PAR MOTS-CLÉS
# ─────────────────────────────────────────────

def categorize_by_keywords(libelle: str, user_mapping: dict) -> str | None:
    """
    Essaie de catégoriser via le mapping utilisateur puis les mots-clés.
    Retourne None si aucun match.
    """
    libelle_lower = libelle.lower()
    key = normalize_key(libelle)

    # Niveau 1 : mapping utilisateur (exact)
    if key in user_mapping:
        return user_mapping[key]

    # Niveau 1b : mapping utilisateur (partiel)
    for known_key, cat in user_mapping.items():
        if known_key and known_key in key:
            return cat

    # Niveau 2 : mots-clés par défaut
    for categorie, keywords in DEFAULT_MAPPING.items():
        for kw in keywords:
            if kw.lower() in libelle_lower:
                return categorie

    return None


# ─────────────────────────────────────────────
#  CATÉGORISATION PAR IA (Claude API)
# ─────────────────────────────────────────────

def categorize_by_ai(libelles: list[str]) -> dict[str, str]:
    """
    Envoie une liste de libellés Unknown à Claude API.
    Retourne un dict {libelle: categorie}.

    Utilise un seul appel API pour tous les Unknown en batch.
    """
    if not libelles:
        return {}

    categories_list = "\n".join(f"- {c}" for c in ALL_CATEGORIES if c != "Unknown")

    prompt = f"""Tu es un assistant qui catégorise des transactions bancaires françaises.

Voici les catégories disponibles :
{categories_list}

Pour chaque transaction ci-dessous, donne la catégorie la plus appropriée.
Réponds UNIQUEMENT en JSON valide, format : {{"libelle": "categorie", ...}}
Si tu n'es pas sûr, utilise "Unknown".

Transactions à catégoriser :
{chr(10).join(f'- {l}' for l in libelles[:50])}"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            text = data["content"][0]["text"]
            # Extraction du JSON de la réponse
            text = re.sub(r"```json|```", "", text).strip()
            result = json.loads(text)
            # Validation des catégories retournées
            return {
                k: v if v in ALL_CATEGORIES else "Unknown"
                for k, v in result.items()
            }
    except Exception as e:
        print(f"[AI categorizer] Erreur : {e}")

    return {}


# ─────────────────────────────────────────────
#  CATÉGORISATION PRINCIPALE
# ─────────────────────────────────────────────

def categorize_transactions(transactions: list[dict]) -> list[dict]:
    """
    Catégorise toute une liste de transactions.

    Étapes :
      1. Mapping utilisateur (corrections mémorisées) → prioritaire
      2. Mots-clés enrichis (500+ marchands français)
      3. Unknown si aucun match → à corriger manuellement

    Returns:
        La même liste avec le champ "categorie" rempli
    """
    user_mapping = load_user_mapping()

    for t in transactions:
        libelle = t.get("libelle_clean") or t.get("libelle", "")
        cat = categorize_by_keywords(libelle, user_mapping)
        t["categorie"] = cat or "Unknown"

    return transactions
