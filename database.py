"""
database.py — Couche de persistance SQLite
==========================================
Toutes les interactions avec la base de données passent par ce module.

Schéma :
  transactions (
    id TEXT PRIMARY KEY,       -- UUID unique
    date TEXT,                 -- "YYYY-MM-DD"
    mois TEXT,                 -- "YYYY-MM" pour filtres
    libelle TEXT,              -- Libellé brut banque
    libelle_clean TEXT,        -- Libellé nettoyé
    montant REAL,              -- Float positif
    type TEXT,                 -- "debit" ou "credit"
    personne TEXT,             -- "Cerise" ou "Loïc"
    banque TEXT,               -- "BoursoBank" ou "BNP Paribas"
    categorie TEXT,            -- Catégorie (peut évoluer)
    corrige_manuellement INTEGER  -- 0 ou 1
  )

Le fichier DB est stocké dans /data/couplefinance.db
Sur Render, ce dossier sera monté sur un disque persistant.
"""

import sqlite3
import os

# Chemin de la base — /data/ sera le disque persistant sur Render
DB_PATH = os.environ.get("DB_PATH", os.path.join("data", "couplefinance.db"))


def get_connection():
    """Retourne une connexion SQLite avec row_factory pour accès par nom de colonne."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    return conn


def init_db():
    """
    Crée la table transactions si elle n'existe pas.
    Appelé au démarrage de l'app.
    """
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                mois TEXT NOT NULL,
                libelle TEXT,
                libelle_clean TEXT,
                montant REAL NOT NULL,
                type TEXT NOT NULL,
                personne TEXT NOT NULL,
                banque TEXT,
                categorie TEXT DEFAULT 'Unknown',
                corrige_manuellement INTEGER DEFAULT 0
            )
        """)
        # Index sur mois et personne pour les requêtes fréquentes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mois ON transactions(mois)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_personne ON transactions(personne)")
        conn.commit()


def insert_transactions(transactions: list[dict]):
    """
    Insère une liste de transactions.
    Utilise INSERT OR IGNORE pour éviter les doublons (basé sur l'id UUID).

    Args:
        transactions: Liste de dicts au format normalisé
    """
    with get_connection() as conn:
        conn.executemany("""
            INSERT OR IGNORE INTO transactions
            (id, date, mois, libelle, libelle_clean, montant, type, personne, banque, categorie, corrige_manuellement)
            VALUES (:id, :date, :mois, :libelle, :libelle_clean, :montant, :type, :personne, :banque, :categorie, :corrige_manuellement)
        """, [
            {**t, "corrige_manuellement": 1 if t.get("corrige_manuellement") else 0}
            for t in transactions
        ])
        conn.commit()


def update_categorie(transaction_id: str, categorie: str):
    """Met à jour la catégorie d'une transaction et la marque comme corrigée."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE transactions
            SET categorie = ?, corrige_manuellement = 1
            WHERE id = ?
        """, (categorie, transaction_id))
        conn.commit()


def get_mois_disponibles() -> list[str]:
    """Retourne la liste des mois disponibles triés du plus récent au plus ancien."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT mois FROM transactions ORDER BY mois DESC"
        ).fetchall()
    return [r["mois"] for r in rows]


def get_transactions(mois: str = None, personne: str = None) -> list[dict]:
    """
    Récupère les transactions avec filtres optionnels.

    Args:
        mois:     Filtre sur le mois "YYYY-MM" (None = tous les mois)
        personne: Filtre sur "Cerise" ou "Loïc" (None = les deux)

    Returns:
        Liste de dicts triés par date décroissante
    """
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if mois:
        query += " AND mois = ?"
        params.append(mois)
    if personne:
        query += " AND personne = ?"
        params.append(personne)

    query += " ORDER BY date DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


def get_stats(mois: str = None) -> dict:
    """
    Calcule les statistiques agrégées pour le dashboard.

    Retourne :
        total_depenses     → float (total débits)
        total_revenus      → float (total crédits)
        solde              → float (revenus - dépenses)
        par_categorie      → dict {categorie: montant}
        par_personne       → dict {personne: {depenses, revenus}}
        evolution_mensuelle → list [{mois, depenses, revenus}]
        top_depenses       → list des 5 plus grosses dépenses
    """
    transactions = get_transactions(mois=mois)

    debits  = [t for t in transactions if t["type"] == "debit"]
    credits = [t for t in transactions if t["type"] == "credit"]

    total_depenses = sum(t["montant"] for t in debits)
    total_revenus  = sum(t["montant"] for t in credits)

    # ── Par catégorie (débits seulement) ──
    par_categorie = {}
    for t in debits:
        cat = t["categorie"] or "Unknown"
        par_categorie[cat] = par_categorie.get(cat, 0) + t["montant"]
    # Tri par montant décroissant
    par_categorie = dict(sorted(par_categorie.items(), key=lambda x: x[1], reverse=True))

    # ── Par personne ──
    par_personne = {}
    for t in transactions:
        p = t["personne"]
        if p not in par_personne:
            par_personne[p] = {"depenses": 0, "revenus": 0}
        if t["type"] == "debit":
            par_personne[p]["depenses"] += t["montant"]
        else:
            par_personne[p]["revenus"] += t["montant"]

    # ── Évolution mensuelle (tous les mois en base) ──
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT mois,
                   SUM(CASE WHEN type='debit' THEN montant ELSE 0 END) as depenses,
                   SUM(CASE WHEN type='credit' THEN montant ELSE 0 END) as revenus
            FROM transactions
            GROUP BY mois
            ORDER BY mois ASC
        """).fetchall()
    evolution = [{"mois": r["mois"], "depenses": r["depenses"], "revenus": r["revenus"]} for r in rows]

    # ── Top 5 dépenses ──
    top_depenses = sorted(debits, key=lambda t: t["montant"], reverse=True)[:5]

    return {
        "total_depenses": round(total_depenses, 2),
        "total_revenus": round(total_revenus, 2),
        "solde": round(total_revenus - total_depenses, 2),
        "nb_transactions": len(transactions),
        "nb_unknown": sum(1 for t in transactions if t["categorie"] == "Unknown"),
        "par_categorie": {k: round(v, 2) for k, v in par_categorie.items()},
        "par_personne": {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in par_personne.items()},
        "evolution_mensuelle": evolution,
        "top_depenses": top_depenses,
    }
