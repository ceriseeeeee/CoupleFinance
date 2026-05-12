import os, json, uuid

from parser_bourso import parse_bourso_pdf
from parser_bnp import parse_bnp_pdf
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
            elif "BNP PARIBAS" in text or "RELEVE DE COMPTE" in text or "RELEVEDECOMPTE" in text or "BNPAFRPPXXX" in text:
                return "bnp"
    except Exception:
        pass
    return "unknown"


def process_upload(files, personne: str) -> dict:
    """Parse les fichiers, catégorise les transactions et crée une session JSON.

    Retourne un dict avec success/error, session_id, count, unknown_count.
    """
    all_transactions = []

    for file in files:
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        try:
            if file.filename.lower().endswith(".csv"):
                from parser_csv import parse_csv
                transactions = parse_csv(filepath, personne)
            elif file.filename.lower().endswith(".pdf"):
                banque = detect_bank(filepath)
                if banque == "bourso":
                    transactions = parse_bourso_pdf(filepath, personne)
                elif banque == "bnp":
                    transactions = parse_bnp_pdf(filepath, personne)
                else:
                    continue
            else:
                continue

            all_transactions.extend(transactions)
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    if not all_transactions:
        return {"error": "Aucune transaction extraite"}

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
    }
