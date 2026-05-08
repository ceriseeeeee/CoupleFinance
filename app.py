"""
app.py — Application Flask CoupleFinance v2
============================================
Routes :
  GET  /              → Dashboard principal
  GET  /import        → Page d'import de PDFs
  POST /upload        → Traitement des PDFs
  GET  /validate/<id> → Validation des transactions
  POST /api/correct   → Correction d'une catégorie
  GET  /api/stats     → Stats JSON pour le dashboard
  GET  /api/transactions → Transactions JSON filtrées
"""

from flask import Flask, render_template, request, jsonify, session
import os, json, uuid
from datetime import datetime

from parser_bourso import parse_bourso_pdf
from parser_bnp import parse_bnp_pdf
from categorizer import categorize_transactions, save_user_correction
from database import init_db, insert_transactions, update_categorie, get_stats, get_mois_disponibles, get_transactions

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "couplefinance-2026")

UPLOAD_FOLDER = "uploads"
SESSION_FOLDER = "data"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SESSION_FOLDER, exist_ok=True)

# Init de la base au démarrage
init_db()


# ─────────────────────────────────────────────
#  DASHBOARD PRINCIPAL
# ─────────────────────────────────────────────

@app.route("/")
def dashboard():
    """Page dashboard avec graphiques et KPIs."""
    mois_dispo = get_mois_disponibles()
    mois_selectionne = request.args.get("mois", mois_dispo[0] if mois_dispo else None)
    stats = get_stats(mois=mois_selectionne) if mois_dispo else {}
    transactions = get_transactions(mois=mois_selectionne) if mois_dispo else []
    return render_template("dashboard.html",
                           mois_dispo=mois_dispo,
                           mois_selectionne=mois_selectionne,
                           stats=stats,
                           transactions=transactions)


# ─────────────────────────────────────────────
#  PAGE IMPORT
# ─────────────────────────────────────────────

@app.route("/import")
def import_page():
    return render_template("index.html")


# ─────────────────────────────────────────────
#  UPLOAD & TRAITEMENT PDF + CSV
# ─────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("pdfs")
    personne = request.form.get("personne")

    if not files or not personne:
        return jsonify({"error": "Fichiers ou personne manquants"}), 400

    all_transactions = []

    for file in files:
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        if file.filename.endswith(".csv"):
            from parser_csv import parse_csv
            transactions = parse_csv(filepath, personne)
        elif file.filename.endswith(".pdf"):
            banque = detect_bank(filepath)
            if banque == "bourso":
                transactions = parse_bourso_pdf(filepath, personne)
            elif banque == "bnp":
                transactions = parse_bnp_pdf(filepath, personne)
            else:
                os.remove(filepath)
                continue
        else:
            os.remove(filepath)
            continue

        all_transactions.extend(transactions)
        os.remove(filepath)

    if not all_transactions:
        return jsonify({"error": "Aucune transaction extraite"}), 400

    all_transactions = categorize_transactions(all_transactions)

    # Stockage session temporaire pour la validation
    session_id = str(uuid.uuid4())
    session_file = os.path.join(SESSION_FOLDER, f"session_{session_id}.json")
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(all_transactions, f, ensure_ascii=False, indent=2)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "count": len(all_transactions),
        "unknown_count": sum(1 for t in all_transactions if t["categorie"] == "Unknown")
    })


def detect_bank(filepath: str) -> str:
    import pdfplumber
    try:
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""
            if "BoursoBank" in text or "Boursorama" in text:
                return "bourso"
            elif "BNP PARIBAS" in text or "RELEVE DE COMPTE" in text or "RELEVEDECOMPTE" in text or "BNPAFRPPXXX" in text:
                return "bnp"
    except Exception:
        pass
    return "unknown"


# ─────────────────────────────────────────────
#  VALIDATION
# ─────────────────────────────────────────────

@app.route("/validate/<session_id>")
def validate(session_id):
    session_file = os.path.join(SESSION_FOLDER, f"session_{session_id}.json")
    if not os.path.exists(session_file):
        return "Session introuvable", 404

    with open(session_file, "r", encoding="utf-8") as f:
        transactions = json.load(f)

    stats = {
        "total": len(transactions),
        "unknown": sum(1 for t in transactions if t["categorie"] == "Unknown"),
        "categorized": sum(1 for t in transactions if t["categorie"] != "Unknown"),
        "total_debit": sum(t["montant"] for t in transactions if t["type"] == "debit"),
        "total_credit": sum(t["montant"] for t in transactions if t["type"] == "credit"),
    }

    return render_template("validate.html",
                           transactions=transactions,
                           session_id=session_id,
                           stats=stats)
# ─────────────────────────────────────────────
#  API — Correction catégorie (session)
# ─────────────────────────────────────────────

@app.route("/api/correct", methods=["POST"])
def correct():
    data = request.json
    session_id = data.get("session_id")
    transaction_id = data.get("transaction_id")
    new_category = data.get("categorie")

    # Mise à jour dans la session temporaire
    if session_id:
        session_file = os.path.join(SESSION_FOLDER, f"session_{session_id}.json")
        if os.path.exists(session_file):
            with open(session_file, "r", encoding="utf-8") as f:
                transactions = json.load(f)
            for t in transactions:
                if t["id"] == transaction_id:
                    save_user_correction(t["libelle"], new_category)
                    t["categorie"] = new_category
                    t["corrige_manuellement"] = True
                    break
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(transactions, f, ensure_ascii=False, indent=2)

    # Mise à jour en base si déjà sauvegardé
    update_categorie(transaction_id, new_category)

    return jsonify({"success": True})


# ─────────────────────────────────────────────
#  API — Validation finale → sauvegarde en DB
# ─────────────────────────────────────────────

@app.route("/api/save/<session_id>", methods=["POST"])
def save_to_db(session_id):
    """Sauvegarde les transactions validées en base et supprime la session."""
    session_file = os.path.join(SESSION_FOLDER, f"session_{session_id}.json")
    if not os.path.exists(session_file):
        return jsonify({"error": "Session introuvable"}), 404

    with open(session_file, "r", encoding="utf-8") as f:
        transactions = json.load(f)

    insert_transactions(transactions)
    os.remove(session_file)

    return jsonify({"success": True, "saved": len(transactions)})


# ─────────────────────────────────────────────
#  API — Stats JSON pour le dashboard
# ─────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    mois = request.args.get("mois")
    return jsonify(get_stats(mois=mois))


# ─────────────────────────────────────────────
#  API — Transactions JSON filtrées
# ─────────────────────────────────────────────

@app.route("/api/transactions")
def api_transactions():
    mois = request.args.get("mois")
    personne = request.args.get("personne")
    transactions = get_transactions(mois=mois, personne=personne)
    return jsonify(transactions)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
