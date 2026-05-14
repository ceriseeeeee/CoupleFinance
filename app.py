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

from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime

from categorizer import save_user_correction, ALL_CATEGORIES
from upload_service import process_upload
from database import (init_db, insert_transactions, update_categorie,
                      get_stats, get_mois_disponibles, get_transactions,
                      save_session, get_session, update_session, delete_session)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "couplefinance-2026")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Init de la base au démarrage
init_db()


# ─────────────────────────────────────────────
#  DASHBOARD PRINCIPAL
# ─────────────────────────────────────────────

@app.route("/")
def dashboard():
    """Page dashboard avec graphiques et KPIs."""
    mois_dispo = get_mois_disponibles()
    mois_selectionne = request.args.get("mois") or None
    personne_filtre = request.args.get("personne") or None
    page_active = request.args.get("page", "overview")
    if page_active not in ("overview", "transactions", "budget", "savings"):
        page_active = "overview"
    stats = get_stats(mois=mois_selectionne, personne=personne_filtre) if mois_dispo else {}
    transactions = get_transactions(mois=mois_selectionne, personne=personne_filtre) if mois_dispo else []
    return render_template("dashboard.html",
                           mois_dispo=mois_dispo,
                           mois_selectionne=mois_selectionne,
                           personne_filtre=personne_filtre,
                           page_active=page_active,
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
    result, status = process_upload(files, personne)
    return jsonify(result), status


# ─────────────────────────────────────────────
#  VALIDATION
# ─────────────────────────────────────────────

@app.route("/validate/<session_id>")
def validate(session_id):
    transactions = get_session(session_id)
    if transactions is None:
        return "Session introuvable", 404

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
    type_depense = data.get("type_depense")
    if new_category not in ALL_CATEGORIES:
        return jsonify({"error": "Catégorie invalide"}), 400

    # Mise à jour dans la session temporaire
    if session_id:
        transactions = get_session(session_id)
        if transactions is not None:
            for t in transactions:
                if t["id"] == transaction_id:
                    t["categorie"] = new_category
                    t["corrige_manuellement"] = True
                    if type_depense is not None:
                        t["type_depense"] = type_depense
                    break
            update_session(session_id, transactions)

    # Mise à jour en base si déjà sauvegardé
    update_categorie(transaction_id, new_category, type_depense)

    if new_category != "Unknown":
        libelle = data.get("libelle", "")
        if libelle:
            save_user_correction(libelle, new_category)

    return jsonify({"success": True})


# ─────────────────────────────────────────────
#  API — Validation finale → sauvegarde en DB
# ─────────────────────────────────────────────

@app.route("/api/save/<session_id>", methods=["POST"])
def save_to_db(session_id):
    """Sauvegarde les transactions validées en base et supprime la session."""
    transactions = get_session(session_id)
    if transactions is None:
        return jsonify({"error": "Session introuvable"}), 404

    inserted = insert_transactions(transactions)
    delete_session(session_id)

    doublons = len(transactions) - inserted
    return jsonify({"success": True, "saved": inserted, "doublons": doublons})


# ─────────────────────────────────────────────
#  API — Stats JSON pour le dashboard
# ─────────────────────────────────────────────

@app.route("/api/dashboard-data")
def api_dashboard_data():
    """Retourne stats + transactions filtrées par mois et/ou personne."""
    mois = request.args.get("mois") or None
    personne = request.args.get("personne") or None
    transactions = get_transactions(mois=mois, personne=personne)
    stats = get_stats(mois=mois, personne=personne)
    return jsonify({"transactions": transactions, "stats": stats})


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


@app.route("/api/export-csv")
def export_csv():
    import csv, io
    from database import get_transactions
    transactions = get_transactions()
    output = io.StringIO()
    if transactions:
        writer = csv.DictWriter(output, fieldnames=transactions[0].keys(), delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(transactions)
    output.seek(0)
    from datetime import datetime
    from flask import send_file
    filename = f"couplefinance_{datetime.now().strftime('%Y%m')}.csv"
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
