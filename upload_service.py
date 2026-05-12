import os
import json
import uuid
from werkzeug.utils import secure_filename

from parser_bourso import parse_bourso_pdf
from parser_bnp import parse_bnp_pdf
from parser_csv import parse_csv
from categorizer import categorize_transactions

UPLOAD_FOLDER = "uploads"
SESSION_FOLDER = "data"


def detect_bank(filepath: str) -> str:
    import pdfplumber

    try:
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""

            if "BoursoBank" in text or "Boursorama" in text:
                return "bourso"

            if (
                "BNP PARIBAS" in text
                or "RELEVE DE COMPTE" in text
                or "RELEVEDECOMPTE" in text
                or "BNPAFRPPXXX" in text
            ):
                return "bnp"

    except Exception:
        pass

    return "unknown"


def process_upload(files, personne: str) -> tuple[dict, int]:
    all_transactions = []

    for file in files:
        safe_name = secure_filename(file.filename)
        filename = f"{uuid.uuid4()}_{safe_name}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        file.save(filepath)

        try:
            if file.filename.lower().endswith(".csv"):
                transactions = parse_csv(filepath, personne)

            elif file.filename.lower().endswith(".pdf"):
                banque = detect_bank(filepath)

                if banque == "bourso":
                    transactions = parse_bourso_pdf(filepath, personne)
                elif banque == "bnp":
                    transactions = parse_bnp_pdf(filepath, personne)
                else:
                    transactions = []

            else:
                transactions = []

            all_transactions.extend(transactions)

        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    if not all_transactions:
        return {"error": "Aucune transaction extraite"}, 400

    all_transactions = categorize_transactions(all_transactions)

    session_id = str(uuid.uuid4())
    session_file = os.path.join(SESSION_FOLDER, f"session_{session_id}.json")

    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(all_transactions, f, ensure_ascii=False, indent=2)

    return {
        "success": True,
        "session_id": session_id,
        "count": len(all_transactions),
        "unknown_count": sum(1 for t in all_transactions if t["categorie"] == "Unknown"),
    }, 200
