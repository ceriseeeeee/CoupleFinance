"""
categorizer.py — Catégorisation v5
====================================
Catégories personnalisées Cerise & Loïc :
  Loyer, Appartement, Abonnements, Électricité, Transport,
  Shopping, Courses & Alimentation, Eating out, Santé,
  Divertissements & Loisirs, Épargne, Bénin Voyage,
  Voyage Couple, Revenus, Virements, Unknown
"""

import json
import os
import re

USER_MAPPING_FILE = os.path.join("data", "user_mapping.json")

# ─────────────────────────────────────────────
#  CATÉGORIES DISPONIBLES
# ─────────────────────────────────────────────

CATEGORIES_COMMUNES = {
    "Loyer", "Appartement", "Électricité", "Bénin Voyage", "Voyage Couple", "Épargne"
}

CATEGORIES_PERSO = {
    "Transport", "Shopping", "Abonnements", "Courses & Alimentation",
    "Eating out", "Santé", "Divertissements & Loisirs", "Virements", "Revenus", "Unknown"
}

ALL_CATEGORIES = [
    "Loyer",
    "Appartement",
    "Abonnements",
    "Électricité",
    "Transport",
    "Shopping",
    "Courses & Alimentation",
    "Eating out",
    "Santé",
    "Divertissements & Loisirs",
    "Épargne",
    "Bénin Voyage",
    "Voyage Couple",
    "Revenus",
    "Virements",
    "Unknown",
]

# ─────────────────────────────────────────────
#  BUDGETS PRÉVUS (pour la page Budget)
# ─────────────────────────────────────────────

BUDGETS_PREVUS = {
    "Loyer":                    {"montant": 1075, "qui": "Loïc",   "commun": False},
    "Appartement":              {"montant": 70,   "qui": "Commun", "commun": True},
    "Abonnements":              {"montant": 181,  "qui": "Séparé", "commun": False,
                                 "detail": {"Cerise": 55, "Loïc": 126}},
    "Électricité":              {"montant": 100,  "qui": "Cerise", "commun": False},
    "Transport":                {"montant": 50,   "qui": "Commun", "commun": True},
    "Shopping":                 {"montant": 200,  "qui": "Commun", "commun": True},
    "Courses & Alimentation":   {"montant": 300,  "qui": "Commun", "commun": True},
    "Eating out":               {"montant": 245,  "qui": "Commun", "commun": True},
    "Santé":                    {"montant": 25,   "qui": "Commun", "commun": True},
    "Divertissements & Loisirs":{"montant": 50,   "qui": "Commun", "commun": True},
    "Épargne":                  {"montant": 400,  "qui": "Commun", "commun": True},
    "Bénin Voyage":             {"montant": 200,  "qui": "Commun", "commun": True},
    "Voyage Couple":            {"montant": 200,  "qui": "Commun", "commun": True},
}

# ─────────────────────────────────────────────
#  MAPPING MOTS-CLÉS
# ─────────────────────────────────────────────

DEFAULT_MAPPING = {
    "Loyer": [
        "loyer", "bnppi residences", "residence principale",
        "quittance", "proprietaire",
    ],

    "Appartement": [
        "washin", "laverie", "laundry", "ikea", "maisons du monde",
        "but ", "conforama", "leroy merlin", "castorama", "bricorama",
        "residence servi", "charges", "syndic", "bricolage",
        "amazon", "amazon payments",  # souvent achats maison
    ],

    "Abonnements": [
        "disney plus", "disney+", "spotify", "netflix", "amazon prime",
        "claude.ai", "google play", "apple.com", "apple.com/bill",
        "uber *one", "uber one", "deezer", "canal+", "canal plus",
        "youtube premium", "twitch", "adobe", "microsoft", "office 365",
        "icloud", "dropbox", "notion", "sfr", "orange", "bouygues",
        "free mobile", "lycamobile", "basic fit", "keepcool",
        "fitness park", "moving", "bitstack", "bitstack sas",
        "service navigo", "navigo",
    ],

    "Électricité": [
        "edf", "engie", "electricite", "electricité", "gaz",
        "eau ", "veolia", "suez", "direct energie",
    ],

    "Transport": [
        "sncf", "sncf-voyageurs", "oui.sncf", "tgv", "ouigo",
        "intercites", "thalys", "eurostar",
        "uber * pending", "ubr* pending", "uber pending",
        "taxi", "blablacar", "autoroutes", "vinci autoroutes",
        "sanef", "area", "parking", "peage",
        "air france", "easyjet", "ryanair", "transavia", "volotea",
        "aeroport", "navette", "autoroutes du s",
        "velib", "lime", "bird", "tier",
    ],

    "Shopping": [
        "zara", "zara.com", "primark", "shein", "eur.shein",
        "aliexpress", "asos", "zalando", "vinted", "mgp*vinted",
        "c et a", "h m hennes", "h&m", "bershka", "bershka.com",
        "pull and bear", "stradivarius", "mango", "uniqlo",
        "cos ", "arket", "monki", "new look", "promod", "kiabi",
        "la halle", "fnac", "darty", "boulanger",
        "apple store", "samsung", "fnac.com",
        "les quatre temps", "westfield",
        "normal paris", "normal ", "action ", "gifi", "tati",
        "sephora", "marionnaud", "nocibe", "adopt", "yves rocher",
        "rituals", "notino", "notino.fr", "sc-lucystyle", "lucystyle",
        "valthilde", "phie benamran", "sc-bonne",
        "iq concept", "2a retail", "dolaka internatio",
        "italie sport", "italie seine",
    ],

    "Courses & Alimentation": [
        "leclerc", "carrefour", "lidl", "aldi", "monoprix", "franprix",
        "intermarche", "casino", "picard", "la fourche", "biocoop",
        "naturalia", "grand frais", "simply market", "super u",
        "hyper u", "auchan", "cora", "match", "netto", "leader price",
        "g20", "8 a huit", "proxi", "vival", "spar",
        "grenier a pain", "patisserie", "boulangerie", "baguette",
        "paul ", "eric kayser", "maison landemaine",
        "m.a. vanille", "les gourmandises", "comptoir belge",
        "asiamart", "douceurs trad", "chapanda",
        "epicerie", "traiteur", "primeur",
        "la fourche distri", "alatone",
    ],

    "Eating out": [
        "mcdonald", "mcdo", "burger king", "kfc", "subway",
        "five guys", "o tacos", "tacos", "kebab",
        "pizza hut", "dominos", "pizza",
        "uber * eats", "uber *eats", "ubereats", "deliveroo",
        "just eat", "uber eats", "uber  eats",
        "nyx*compassgroup", "nyx*compass", "compassgroup",
        "api restauration", "express coffee", "coffee",
        "starbucks", "cotti coffee", "momen tea", "bubble tea",
        "mae bowl", "yatai ramen", "ramen", "thym et olive",
        "pepperico", "indiana", "veng hour", "lili food",
        "bolkiri", "degray", "sunday*le paradis", "la brigade",
        "ab copains", "xft reaumur", "pretamanger", "pret a manger",
        "sem tam cine", "somasando", "sama ", "roll in",
        "wesley chatel", "tenz", "full plate", "french s style",
        "l auberge", "popotte", "dmc ", "q102", "bonne baguette",
        "o crousti", "patisserie bou", "ivoire restos",
    ],

    "Santé": [
        "pharmacie", "medecin", "docteur", "dentiste", "opticien",
        "mutuelle", "secu", "cpam", "ameli", "cardif iard",
        "pointgyn", "gyneco", "laboratoire", "analyse",
        "radio", "scanner", "kiné", "kinesitherapie", "osteo",
    ],

    "Divertissements & Loisirs": [
        "cinema", "ugc", "mk2", "pathe", "gaumont",
        "musee", "theatre", "concert", "spectacle",
        "cultura", "gibert", "librairie",
        "jeux video", "steam", "playstation", "xbox",
        "bowling", "karting", "laser game", "escape game",
        "noel la villette", "sumup *loisirs", "loisirs",
        "parc", "zoo", "aquarium", "disneyland",
        "koepfers", "steinbuc",
    ],

    "Épargne": [
        "livret", "epargne", "livret a", "assurance vie",
        "bourse", "investissement", "placement", "pea ", "per ",
    ],

    "Bénin Voyage": [
        "benin", "bénin", "tdf emis", "taptap", "wari",
        "western union", "moneygram", "transfert international",
        "vir etranger",
    ],

    "Voyage Couple": [
        "hotel", "airbnb", "booking", "expedia",
        "hostel", "gite", "camping", "location voiture",
        "travel", "voyage couple",
    ],

    "Revenus": [
        "salaire", "heineken entreprise", "mes extras",
        "caf des", "apl", "action logement services",
        "vir sepa recu", "vir sct inst recu",
        "remboursement", "avoir ",
        "prime ", "bonus ", "indemnite",
    ],

    "Virements": [
        "vir inst", "vir sepa", "vir sct",
        "virement depuis boursobank",
        "wero ",
    ],
}


# ─────────────────────────────────────────────
#  MAPPING UTILISATEUR
# ─────────────────────────────────────────────

def load_user_mapping() -> dict:
    """Charge le mapping depuis Supabase ou fichier local."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS category_corrections (
                    libelle_key TEXT PRIMARY KEY,
                    categorie TEXT NOT NULL
                )
            """)
            conn.commit()
            cur.execute("SELECT libelle_key, categorie FROM category_corrections")
            rows = cur.fetchall()
            conn.close()
            return {r[0]: r[1] for r in rows}
        except Exception as e:
            print(f"[category_corrections] Erreur: {e}")
            return {}
    else:
        os.makedirs("data", exist_ok=True)
        if os.path.exists(USER_MAPPING_FILE):
            with open(USER_MAPPING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}


def save_user_correction(libelle: str, categorie: str):
    """Sauvegarde une correction de façon persistante (Supabase ou local)."""
    key = normalize_key(libelle)
    if not key:
        return
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS category_corrections (
                    libelle_key TEXT PRIMARY KEY,
                    categorie TEXT NOT NULL
                )
            """)
            cur.execute("""
                INSERT INTO category_corrections (libelle_key, categorie)
                VALUES (%s, %s)
                ON CONFLICT (libelle_key) DO UPDATE SET categorie = EXCLUDED.categorie
            """, (key, categorie))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[category_corrections] Erreur sauvegarde: {e}")
    else:
        os.makedirs("data", exist_ok=True)
        mapping = {}
        if os.path.exists(USER_MAPPING_FILE):
            with open(USER_MAPPING_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        mapping[key] = categorie
        with open(USER_MAPPING_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)


def normalize_key(libelle: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", libelle.lower()).strip()


# ─────────────────────────────────────────────
#  CATÉGORISATION
# ─────────────────────────────────────────────

def categorize_by_keywords(libelle: str, user_mapping: dict) -> str | None:
    libelle_lower = libelle.lower()
    key = normalize_key(libelle)

    # Niveau 1 : mapping utilisateur
    if key in user_mapping:
        return user_mapping[key]
    for known_key, cat in user_mapping.items():
        if known_key and known_key in key:
            return cat

    # Niveau 2 : mots-clés
    for categorie, keywords in DEFAULT_MAPPING.items():
        for kw in keywords:
            if kw.lower() in libelle_lower:
                return categorie

    return None


def categorize_transactions(transactions: list[dict]) -> list[dict]:
    user_mapping = load_user_mapping()
    for t in transactions:
        libelle = t.get("libelle_clean") or t.get("libelle", "")
        cat = categorize_by_keywords(libelle, user_mapping)
        t["categorie"] = cat or "Unknown"
        if t["categorie"] in CATEGORIES_COMMUNES:
            t["type_depense"] = "commune"
        else:
            t["type_depense"] = "perso"
    return transactions
