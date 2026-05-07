# CoupleFinance 💚
## Application de traitement de relevés bancaires

---

### Structure des fichiers

```
couplefinance/
├── app.py              ← Serveur Flask + toutes les routes
├── parser_bourso.py    ← Extraction des PDFs BoursoBank
├── parser_bnp.py       ← Extraction des PDFs BNP Paribas
├── categorizer.py      ← Catégorisation auto + apprentissage
├── exporter.py         ← Génération du CSV pour Power BI
├── requirements.txt    ← Dépendances Python
├── templates/
│   ├── index.html      ← Page d'upload
│   └── validate.html   ← Page de validation/correction
├── data/               ← Sessions temporaires + mapping appris (auto-créé)
├── uploads/            ← PDFs temporaires (auto-créé, nettoyé après traitement)
└── exports/            ← CSVs générés (auto-créé)
```

---

### Installation & lancement

```bash
# 1. Aller dans le dossier du projet
cd couplefinance

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'application
python app.py

# 5. Ouvrir dans le navigateur
# http://localhost:5000
```

---

### Utilisation

1. **Choisir la personne** (Cerise ou Loïc) — important pour l'attribution dans Power BI
2. **Déposer les PDFs** — BoursoBank et BNP détectés automatiquement
3. **Valider les transactions** — Les Unknown sont surlignés en orange
4. **Corriger les Unknown** — Le select mémorise ta correction pour les prochains imports
5. **Exporter** — CSV prêt à charger dans Power BI

---

### Comment ajouter une banque

1. Créer un fichier `parser_mabanque.py` en suivant le modèle de `parser_bourso.py`
2. Dans `app.py`, ajouter la détection dans `detect_bank()` et le cas dans `upload()`

---

### Déploiement en ligne (Render — gratuit)

1. Créer un compte sur [render.com](https://render.com)
2. Nouveau service → Web Service → connecter ton repo GitHub
3. Build command : `pip install -r requirements.txt`
4. Start command : `gunicorn app:app`
5. C'est tout — URL partageable avec Loïc
