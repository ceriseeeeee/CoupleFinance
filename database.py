"""
database.py — Couche de persistance PostgreSQL (Supabase)
==========================================================
Utilise psycopg2 pour se connecter à Supabase en production.
Fallback sur SQLite en local si DATABASE_URL n'est pas défini.

Variables d'environnement :
  DATABASE_URL : URL PostgreSQL Supabase (obligatoire en prod)
"""

import os
import uuid

DATABASE_URL = os.environ.get("DATABASE_URL")

# ─────────────────────────────────────────────
#  CONNEXION — PostgreSQL ou SQLite selon l'env
# ─────────────────────────────────────────────

def get_connection():
    """
    Retourne une connexion à la base de données.
    - En production (Render) : PostgreSQL via Supabase
    - En local : SQLite fallback
    """
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        import sqlite3
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(os.path.join("data", "couplefinance.db"))
        conn.row_factory = sqlite3.Row
        return conn


def is_postgres():
    return bool(DATABASE_URL)


def placeholder(n=1):
    """Retourne le bon placeholder selon la DB (%s pour PG, ? pour SQLite)."""
    if is_postgres():
        return ','.join(['%s'] * n) if n > 1 else '%s'
    return ','.join(['?'] * n) if n > 1 else '?'


# ─────────────────────────────────────────────
#  INITIALISATION DE LA BASE
# ─────────────────────────────────────────────

def init_db():
    """Crée les tables transactions et user_mapping si elles n'existent pas."""
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mois ON transactions(mois)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_personne ON transactions(personne)")

        if is_postgres():
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_mapping (
                    id SERIAL PRIMARY KEY,
                    personne TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    couleur TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    personne TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    couleur TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  INSERT
# ─────────────────────────────────────────────

def insert_transactions(transactions: list[dict]):
    """
    Insère les transactions en ignorant les doublons (basé sur l'id UUID).
    Compatible PostgreSQL et SQLite.
    """
    if not transactions:
        return

    conn = get_connection()
    try:
        cur = conn.cursor()

        if is_postgres():
            for t in transactions:
                cur.execute("""
                    INSERT INTO transactions
                    (id, date, mois, libelle, libelle_clean, montant, type, personne, banque, categorie, corrige_manuellement)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    t['id'], t['date'], t['mois'], t.get('libelle'), t.get('libelle_clean'),
                    t['montant'], t['type'], t['personne'], t.get('banque'),
                    t.get('categorie', 'Unknown'),
                    1 if t.get('corrige_manuellement') else 0
                ))
        else:
            for t in transactions:
                cur.execute("""
                    INSERT OR IGNORE INTO transactions
                    (id, date, mois, libelle, libelle_clean, montant, type, personne, banque, categorie, corrige_manuellement)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    t['id'], t['date'], t['mois'], t.get('libelle'), t.get('libelle_clean'),
                    t['montant'], t['type'], t['personne'], t.get('banque'),
                    t.get('categorie', 'Unknown'),
                    1 if t.get('corrige_manuellement') else 0
                ))

        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  UPDATE
# ─────────────────────────────────────────────

def update_categorie(transaction_id: str, categorie: str):
    """Met à jour la catégorie d'une transaction."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        p = '%s' if is_postgres() else '?'
        cur.execute(f"""
            UPDATE transactions
            SET categorie = {p}, corrige_manuellement = 1
            WHERE id = {p}
        """, (categorie, transaction_id))
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  REQUÊTES
# ─────────────────────────────────────────────

def get_mois_disponibles() -> list[str]:
    """Retourne la liste des mois disponibles, du plus récent au plus ancien."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT mois FROM transactions ORDER BY mois DESC")
        rows = cur.fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def get_transactions(mois: str = None, personne: str = None) -> list[dict]:
    """Récupère les transactions avec filtres optionnels."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        p = '%s' if is_postgres() else '?'
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []

        if mois:
            query += f" AND mois = {p}"
            params.append(mois)
        if personne:
            query += f" AND LOWER(personne) = LOWER({p})"
            params.append(personne)

        query += " ORDER BY date DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

        # Conversion en liste de dicts
        if is_postgres():
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in rows]
        else:
            return [dict(row) for row in rows]
    finally:
        conn.close()


def get_stats(mois: str = None, personne: str = None) -> dict:
    """Calcule les statistiques agrégées pour le dashboard."""
    transactions = get_transactions(mois=mois, personne=personne)

    debits  = [t for t in transactions if t['type'] == 'debit']
    credits = [t for t in transactions if t['type'] == 'credit']

    total_depenses = sum(t['montant'] for t in debits)
    total_revenus  = sum(t['montant'] for t in credits)

    # Par catégorie
    par_categorie = {}
    for t in debits:
        cat = t['categorie'] or 'Unknown'
        par_categorie[cat] = par_categorie.get(cat, 0) + t['montant']
    par_categorie = dict(sorted(par_categorie.items(), key=lambda x: x[1], reverse=True))

    # Par personne
    par_personne = {}
    for t in transactions:
        p = t['personne']
        if p not in par_personne:
            par_personne[p] = {'depenses': 0, 'revenus': 0}
        if t['type'] == 'debit':
            par_personne[p]['depenses'] += t['montant']
        else:
            par_personne[p]['revenus'] += t['montant']

    # Évolution mensuelle
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT mois,
                   SUM(CASE WHEN type='debit' THEN montant ELSE 0 END) as depenses,
                   SUM(CASE WHEN type='credit' THEN montant ELSE 0 END) as revenus
            FROM transactions
            GROUP BY mois
            ORDER BY mois ASC
        """)
        rows = cur.fetchall()
        if is_postgres():
            cols = [desc[0] for desc in cur.description]
            evolution = [dict(zip(cols, row)) for row in rows]
        else:
            evolution = [dict(row) for row in rows]
    finally:
        conn.close()

    top_depenses = sorted(debits, key=lambda t: t['montant'], reverse=True)[:5]

    return {
        'total_depenses':     round(total_depenses, 2),
        'total_revenus':      round(total_revenus, 2),
        'solde':              round(total_revenus - total_depenses, 2),
        'nb_transactions':    len(transactions),
        'nb_unknown':         sum(1 for t in transactions if t['categorie'] == 'Unknown'),
        'par_categorie':      {k: round(v, 2) for k, v in par_categorie.items()},
        'par_personne':       {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in par_personne.items()},
        'evolution_mensuelle': evolution,
        'top_depenses':       top_depenses,
    }
