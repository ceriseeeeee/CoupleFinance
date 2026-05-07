"""
exporter.py — Export CSV pour Power BI
=======================================
Génère un CSV propre et standardisé à partir des transactions validées.

Colonnes exportées (optimisées pour Power BI) :
  date, mois, libelle_clean, montant, type, personne, banque, categorie, corrige_manuellement

Le CSV utilise le séparateur ";" (standard français pour Excel/Power BI)
et l'encodage UTF-8 BOM pour éviter les problèmes d'accents.
"""

import csv
import os


# Colonnes dans l'ordre exact souhaité dans Power BI
EXPORT_COLUMNS = [
    "date",
    "mois",
    "libelle_clean",
    "montant",
    "type",
    "personne",
    "banque",
    "categorie",
    "corrige_manuellement"
]

# En-têtes lisibles pour Power BI (correspondance colonne → label)
COLUMN_LABELS = {
    "date": "Date",
    "mois": "Mois",
    "libelle_clean": "Libellé",
    "montant": "Montant",
    "type": "Type",
    "personne": "Personne",
    "banque": "Banque",
    "categorie": "Catégorie",
    "corrige_manuellement": "Corrigé manuellement"
}


def export_to_csv(transactions: list[dict], output_path: str):
    """
    Écrit les transactions dans un fichier CSV prêt pour Power BI.

    Args:
        transactions: Liste de dicts transactions validées
        output_path:  Chemin de sortie du fichier CSV

    Le fichier est encodé en UTF-8 BOM (utf-8-sig) pour la compatibilité
    avec Excel français qui attend un BOM pour détecter l'UTF-8.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        # Séparateur ";" : standard français (Power BI et Excel le gèrent)
        writer = csv.DictWriter(
            f,
            fieldnames=EXPORT_COLUMNS,
            delimiter=";",
            extrasaction="ignore"  # Ignore les champs non listés (ex: id, libelle raw)
        )

        # En-tête avec labels lisibles
        writer.writerow({col: COLUMN_LABELS[col] for col in EXPORT_COLUMNS})

        # Tri par date puis par personne pour faciliter la lecture
        sorted_transactions = sorted(
            transactions,
            key=lambda t: (t.get("date", ""), t.get("personne", ""))
        )

        for t in sorted_transactions:
            # Formatage des valeurs avant écriture
            row = {col: format_value(col, t.get(col, "")) for col in EXPORT_COLUMNS}
            writer.writerow(row)


def format_value(column: str, value) -> str:
    """
    Formate une valeur selon son type pour l'export CSV.

    - montant     → "1 032,92" (format français avec espace milliers)
    - bool        → "Oui" / "Non"
    - autres      → str simple
    """
    if column == "montant" and isinstance(value, (int, float)):
        # Format français : virgule décimale, espace comme séparateur milliers
        return f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
        # Résultat : 1032.92 → "1 032,92" (format FR)
        # Note : on fait virgule → espace → point → virgule pour inverser les séparateurs

    if column == "corrige_manuellement":
        return "Oui" if value else "Non"

    return str(value) if value is not None else ""
