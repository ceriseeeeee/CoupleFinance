"""
CoupleFinance - Application principale Flask
============================================
Point d'entrée de l'application. Gère toutes les routes :
  - Upload de PDFs bancaires
  - Extraction + catégorisation des transactions
  - Interface de validation/correction manuelle
  - Export CSV pour Power BI
"""

from flask import Flask, render_template, request, jsonify, send_file, session
import os
import json
import uuid
from datetime import datetime

from parser_bourso import parse_bourso_pdf
from parser_bnp import parse_bnp_pdf
from categorizer import categorize_transactions, save_user_correction
from exporter import export_to_csv

app = Flask(__name__)

# Clé secrète pour les sessions (à changer en prod)
app.secret_key = "couplefinance-secret-key-2026"

# Dossiers de travail
UPLOAD_FOLDER = "uploads"
EXPORT_FOLDER = "exports"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────
#  PAGE D'ACCUEIL — Upload des PDFs
# ─────────────────────────────────────────────

@app.route("/")
def index():
    """Page principale avec le formulaire d'upload."""
    return render_template("index.html")


# ─────────────────────────────────────────────
#  ROUTE — Traitement des PDFs uploadés
# ─────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
def upload():
    """
    Reçoit les PDFs, détecte la banque, extrait les transactions,
    et redirige vers la page de validation.
    """
    files = request.files.getlist("pdfs")
    personne = request.form.get("personne")  # "Cerise" ou "Loïc"
    
    if not files or not personne:
        return jsonify({"error": "Fichiers ou personne manquants"}), 400

    all_transactions = []

    for file in files:
        if not file.filename.endswith(".pdf"):
            continue

        # Sauvegarde temporaire du PDF
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # ── Détection automatique de la banque ──
        # On lit les premiers octets du texte extrait pour identifier la banque
        banque = detect_bank(filepath)

        # ── Parsing selon la banque ──
        if banque == "bourso":
            transactions = parse_bourso_pdf(filepath, personne)
        elif banque == "bnp":
            transactions = parse_bnp_pdf(filepath, personne)
        else:
            # Banque non reconnue → on passe
            os.remove(filepath)
            continue

        all_transactions.extend(transactions)
        os.remove(filepath)  # Nettoyage du fichier temporaire

    if not all_transactions:
        return jsonify({"error": "Aucune transaction extraite"}), 400

    # ── Catégorisation automatique ──
    all_transactions = categorize_transactions(all_transactions)

    # ── Stockage en session pour la page de validation ──
    session_id = str(uuid.uuid4())
    session_file = os.path.join("data", f"session_{session_id}.json")
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(all_transactions, f, ensure_ascii=False, indent=2)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "count": len(all_transactions),
        "unknown_count": sum(1 for t in all_transactions if t["categorie"] == "Unknown")
    })


def detect_bank(filepath: str) -> str:
    """
    Détecte la banque à partir du contenu du PDF.
    Retourne 'bourso', 'bnp', ou 'unknown'.
    """
    import pdfplumber
    try:
        with pdfplumber.open(filepath) as pdf:
            # On lit uniquement la première page pour la détection
            first_page_text = pdf.pages[0].extract_text() or ""
            if "BoursoBank" in first_page_text or "Boursorama" in first_page_text:
                return "bourso"
            elif "BNP PARIBAS" in first_page_text or "RELEVE DE COMPTE" in first_page_text:
                return "bnp"
    except Exception:
        pass
    return "unknown"


# ─────────────────────────────────────────────
#  PAGE — Validation & correction des transactions
# ─────────────────────────────────────────────

@app.route("/validate/<session_id>")
def validate(session_id):
    """
    Affiche toutes les transactions extraites.
    Les Unknown sont mis en avant pour correction.
    """
    session_file = os.path.join("data", f"session_{session_id}.json")
    if not os.path.exists(session_file):
        return "Session introuvable", 404

    with open(session_file, "r", encoding="utf-8") as f:
        transactions = json.load(f)

    # Statistiques pour l'en-tête de page
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
#  API — Correction d'une catégorie
# ─────────────────────────────────────────────

@app.route("/api/correct", methods=["POST"])
def correct():
    """
    Reçoit la correction d'une catégorie par l'utilisateur.
    Met à jour la session ET mémorise le mot-clé pour l'avenir.
    """
    data = request.json
    session_id = data.get("session_id")
    transaction_id = data.get("transaction_id")
    new_category = data.get("categorie")

    session_file = os.path.join("data", f"session_{session_id}.json")
    if not os.path.exists(session_file):
        return jsonify({"error": "Session introuvable"}), 404

    with open(session_file, "r", encoding="utf-8") as f:
        transactions = json.load(f)

    # Mise à jour de la transaction dans la session
    for t in transactions:
        if t["id"] == transaction_id:
            old_libelle = t["libelle"]
            t["categorie"] = new_category
            t["corrige_manuellement"] = True  # Flag pour traçabilité
            
            # Apprentissage : mémorisation du mapping libellé → catégorie
            save_user_correction(old_libelle, new_category)
            break

    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(transactions, f, ensure_ascii=False, indent=2)

    return jsonify({"success": True})


# ─────────────────────────────────────────────
#  API — Export CSV final
# ─────────────────────────────────────────────

@app.route("/api/export/<session_id>", methods=["POST"])
def export(session_id):
    """
    Génère le CSV propre à partir des transactions validées.
    Prêt à être chargé dans Power BI.
    """
    session_file = os.path.join("data", f"session_{session_id}.json")
    if not os.path.exists(session_file):
        return jsonify({"error": "Session introuvable"}), 404

    with open(session_file, "r", encoding="utf-8") as f:
        transactions = json.load(f)

    # Génération du fichier CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"couplefinance_export_{timestamp}.csv"
    output_path = os.path.join(EXPORT_FOLDER, output_filename)

    export_to_csv(transactions, output_path)

    # Nettoyage de la session après export
    os.remove(session_file)

    return send_file(output_path, as_attachment=True, download_name=output_filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
