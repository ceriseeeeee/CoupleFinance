// ══════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  event.currentTarget.classList.add('active');
}

// ══════════════════════════════════════
//  FILTRE LOCAL TRANSACTIONS
// ══════════════════════════════════════
function normalizeName(s) {
  return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function filterTxn(type, btn) {
  document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  document.querySelectorAll('#txn-body tr').forEach(row => {
    let show = true;
    if (type === 'unknown') show = row.dataset.cat === 'Unknown';
    if (type === 'debit')   show = row.dataset.type === 'debit';
    if (type === 'credit')  show = row.dataset.type === 'credit';
    if (type === 'cerise')  show = normalizeName(row.dataset.personne) === 'cerise';
    if (type === 'loic')    show = normalizeName(row.dataset.personne) === 'loic';
    row.style.display = show ? '' : 'none';
  });
}

// ══════════════════════════════════════
//  CHART.JS CONFIG
// ══════════════════════════════════════
Chart.defaults.font.family = 'Nunito';
Chart.defaults.font.size = 12;
Chart.defaults.color = '#9CA3AF';
Chart.defaults.borderColor = '#E8EBF0';

const PALETTE = ['#2ECC9A','#60A5FA','#F87171','#F59E0B','#A78BFA','#34D399','#FB923C','#F472B6','#38BDF8'];

// ══════════════════════════════════════
//  CONSTANTES
// ══════════════════════════════════════
const ALL_CATS = [
  'Loyer','Appartement','Abonnements','Électricité','Transport',
  'Shopping','Courses & Alimentation','Eating out','Santé',
  'Divertissements & Loisirs','Épargne','Bénin Voyage',
  'Voyage Couple','Revenus','Virements','Unknown'
];

const BUDGETS_PREVUS = {
  'Loyer': 1075, 'Appartement': 70, 'Abonnements': 181,
  'Électricité': 100, 'Transport': 50, 'Shopping': 200,
  'Courses & Alimentation': 300, 'Eating out': 245,
  'Santé': 25, 'Divertissements & Loisirs': 50,
  'Épargne': 400, 'Bénin Voyage': 200, 'Voyage Couple': 200
};

// ══════════════════════════════════════
//  INSTANCES CHART (pour destroy/recreate)
// ══════════════════════════════════════
let chartEvolution = null;
let chartCategories = null;
let chartPersonnes = null;
let chartBudget = null;
let chartBudgetPersonne = null;
let chartSavings = null;

function destroyChart(instance) {
  if (instance) instance.destroy();
  return null;
}

// ══════════════════════════════════════
//  UPDATE KPIs
// ══════════════════════════════════════
function updateKPIs(stats) {
  const solde   = stats.solde || 0;
  const revenus = stats.total_revenus || 0;
  const depenses = stats.total_depenses || 0;
  const epargne = Math.max(solde, 0);
  const nbTxn   = stats.nb_transactions || 0;
  const nbUnknown = stats.nb_unknown || 0;

  const soldeEl = document.getElementById('kpi-solde');
  soldeEl.textContent = (solde >= 0 ? '+' : '') + Math.round(solde) + ' €';
  soldeEl.style.color = solde >= 0 ? 'var(--green)' : 'var(--red)';

  document.getElementById('kpi-revenus').textContent  = Math.round(revenus) + ' €';
  document.getElementById('kpi-depenses').textContent = Math.round(depenses) + ' €';
  document.getElementById('kpi-epargne').textContent  = Math.round(epargne) + ' €';
  document.getElementById('kpi-nb-txn').textContent   = nbTxn;

  const nuEl = document.getElementById('kpi-nb-unknown');
  nuEl.textContent = nbUnknown + ' inconnues';
  nuEl.className = 'kpi-sub' + (nbUnknown > 0 ? ' down' : '');
}

// ══════════════════════════════════════
//  UPDATE GRAPHIQUES
// ══════════════════════════════════════
function updateCharts(stats) {
  const evo      = stats.evolution_mensuelle || [];
  const parCat   = stats.par_categorie || {};
  const parPer   = stats.par_personne || {};
  const personnes = Object.keys(parPer);

  // Évolution
  chartEvolution = destroyChart(chartEvolution);
  const elEvo = document.getElementById('chartEvolution');
  if (elEvo && evo.length) {
    chartEvolution = new Chart(elEvo, {
      type: 'line',
      data: {
        labels: evo.map(e => e.mois),
        datasets: [
          { label: 'Revenus',  data: evo.map(e => e.revenus),  borderColor: '#2ECC9A', backgroundColor: 'rgba(46,204,154,.08)', tension: .4, fill: true, pointBackgroundColor: '#2ECC9A', pointRadius: 3 },
          { label: 'Dépenses', data: evo.map(e => e.depenses), borderColor: '#F87171', backgroundColor: 'rgba(248,113,113,.08)', tension: .4, fill: true, pointBackgroundColor: '#F87171', pointRadius: 3 }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, padding: 12 } } }, scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => v + ' €' } } } }
    });
  }

  // Donut catégories
  chartCategories = destroyChart(chartCategories);
  const elCat = document.getElementById('chartCategories');
  const cats = Object.keys(parCat).slice(0, 7);
  if (elCat && cats.length) {
    chartCategories = new Chart(elCat, {
      type: 'doughnut',
      data: { labels: cats, datasets: [{ data: cats.map(k => parCat[k]), backgroundColor: PALETTE, borderWidth: 0, hoverOffset: 6 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, padding: 8, font: { size: 11 } } } } }
    });
  }

  // Barres Cerise vs Loïc
  chartPersonnes = destroyChart(chartPersonnes);
  const elPer = document.getElementById('chartPersonnes');
  if (elPer && personnes.length) {
    chartPersonnes = new Chart(elPer, {
      type: 'bar',
      data: {
        labels: personnes,
        datasets: [
          { label: 'Dépenses', data: personnes.map(p => parPer[p].depenses), backgroundColor: 'rgba(248,113,113,.7)', borderRadius: 6 },
          { label: 'Revenus',  data: personnes.map(p => parPer[p].revenus),  backgroundColor: 'rgba(46,204,154,.7)',  borderRadius: 6 }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, padding: 10 } } }, scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => v + ' €' } } } }
    });
  }

  // Budget taux consommation
  chartBudget = destroyChart(chartBudget);
  const elBud = document.getElementById('chartBudget');
  if (elBud) {
    const budLabels = Object.keys(BUDGETS_PREVUS);
    chartBudget = new Chart(elBud, {
      type: 'bar',
      data: {
        labels: budLabels,
        datasets: [
          { label: 'Prévu',   data: Object.values(BUDGETS_PREVUS),      backgroundColor: 'rgba(96,165,250,.5)', borderRadius: 4 },
          { label: 'Réalisé', data: budLabels.map(l => parCat[l] || 0), backgroundColor: 'rgba(46,204,154,.8)', borderRadius: 4 }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } } }, scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => v + ' €' } } } }
    });
  }

  // Budget par personne
  chartBudgetPersonne = destroyChart(chartBudgetPersonne);
  const elBudPer = document.getElementById('chartBudgetPersonne');
  const cats6 = Object.keys(parCat).slice(0, 6);
  if (elBudPer && personnes.length) {
    chartBudgetPersonne = new Chart(elBudPer, {
      type: 'bar',
      data: {
        labels: cats6,
        datasets: personnes.map((p, i) => ({
          label: p, data: cats6.map(cat => ((stats.par_personne_categorie || {})[p] || {})[cat] || 0),
          backgroundColor: PALETTE[i], borderRadius: 4
        }))
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } } }, scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => v + ' €' } } } }
    });
  }

  // Savings évolution
  chartSavings = destroyChart(chartSavings);
  const elSav = document.getElementById('chartSavings');
  if (elSav && evo.length) {
    chartSavings = new Chart(elSav, {
      type: 'bar',
      data: {
        labels: evo.map(e => e.mois),
        datasets: [{ label: 'Épargne', data: evo.map(e => Math.max(0, e.revenus - e.depenses)), backgroundColor: 'rgba(46,204,154,.7)', borderRadius: 6 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => v + ' €' } } } }
    });
  }
}

// ══════════════════════════════════════
//  UPDATE TABLE TRANSACTIONS
// ══════════════════════════════════════
function esc(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function buildCatSelect(txnId, currentCat) {
  const opts = ALL_CATS.map(c =>
    `<option value="${esc(c)}"${currentCat === c ? ' selected' : ''}>${esc(c)}</option>`
  ).join('');
  return `<select class="cat-select-inline" onchange="correctDashboard('${esc(txnId)}', this.value, this)">${opts}</select>`;
}

function updateTxnTable(transactions) {
  const tbody = document.getElementById('txn-body');
  if (!tbody) return;
  tbody.innerHTML = transactions.map(t => {
    const libelle = esc(t.libelle_clean || t.libelle);
    const montantStr = t.montant.toFixed(2).replace('.', ',');
    const sign = t.type === 'debit' ? '−' : '+';
    const cls  = t.type === 'debit' ? 'neg' : 'pos';
    const unknownCls = t.categorie === 'Unknown' ? 'unknown' : '';
    return `<tr class="${unknownCls}"
              data-type="${esc(t.type)}"
              data-cat="${esc(t.categorie)}"
              data-personne="${esc((t.personne || '').toLowerCase())}"
              data-id="${esc(t.id)}"
              data-libelle="${esc(t.libelle_clean || t.libelle)}">
      <td style="color:var(--muted)">${esc(t.date)}</td>
      <td style="font-weight:500">${libelle}</td>
      <td>${buildCatSelect(t.id, t.categorie)}</td>
      <td>
        <select class="type-select" onchange="correctType('${esc(t.id)}', this.value, this)" data-cat="${esc(t.categorie)}">
          <option value="commune" ${t.type_depense === 'commune' ? 'selected' : ''}>🤝 Commune</option>
          <option value="perso" ${t.type_depense !== 'commune' ? 'selected' : ''}>👤 Perso</option>
        </select>
      </td>
      <td>${esc(t.personne)}</td>
      <td style="color:var(--muted);font-size:.78rem">${esc(t.banque)}</td>
      <td class="${cls}" style="text-align:right">${sign}${montantStr} €</td>
    </tr>`;
  }).join('');
}

// ══════════════════════════════════════
//  UPDATE TOP DÉPENSES
// ══════════════════════════════════════
function updateTopDepenses(tops) {
  const tbody = document.getElementById('top-depenses-body');
  if (!tbody) return;
  tbody.innerHTML = tops.map((t, i) => {
    const libelle = esc(t.libelle_clean || t.libelle);
    const montantStr = t.montant.toFixed(2).replace('.', ',');
    return `<tr>
      <td style="color:var(--muted);font-weight:600;">${i + 1}</td>
      <td style="color:var(--muted)">${esc(t.date)}</td>
      <td style="font-weight:500">${libelle}</td>
      <td>${esc(t.personne)}</td>
      <td><span class="cat-badge">${esc(t.categorie)}</span></td>
      <td class="neg" style="text-align:right">−${montantStr} €</td>
    </tr>`;
  }).join('');
}

// ══════════════════════════════════════
//  UPDATE BUDGET ROWS
// ══════════════════════════════════════
function updateBudgetRows(parCat) {
  document.querySelectorAll('.budget-data-row').forEach(row => {
    const cat    = row.dataset.cat;
    const prevu  = parseInt(row.dataset.prevu) || 0;
    const realise = parCat[cat] || 0;
    const pct    = prevu > 0 ? Math.round((realise / prevu) * 100) : 0;
    const color  = pct > 90 ? '#F87171' : (pct > 70 ? '#F59E0B' : '#2ECC9A');
    const pctCls = pct > 90 ? 'over'   : (pct > 70 ? 'warn'    : 'ok');

    const fill = row.querySelector('.bud-bar-fill');
    fill.style.width      = Math.min(pct, 100) + '%';
    fill.style.background = color;

    row.querySelector('.bud-realise').textContent = Math.round(realise) + ' €';

    const pctEl = row.querySelector('.bud-pct');
    pctEl.textContent = pct + '%';
    pctEl.className   = `bud-pct ${pctCls}`;
  });
}

// ══════════════════════════════════════
//  UPDATE SAVINGS
// ══════════════════════════════════════
function updateSavings(stats) {
  const epargne = Math.max(stats.solde || 0, 0);
  const savPct  = Math.min(Math.round((epargne / 400) * 100), 100);

  const elAmt = document.getElementById('sav-epargne');
  if (elAmt) elAmt.textContent = Math.round(epargne) + ' €';

  const elBar = document.getElementById('sav-bar');
  if (elBar) {
    elBar.style.width      = savPct + '%';
    elBar.style.background = savPct < 50 ? '#F87171' : '#2ECC9A';
  }

  const elPct = document.getElementById('sav-pct');
  if (elPct) elPct.textContent = savPct + "% de l'objectif";
}

// ══════════════════════════════════════
//  UPDATE DASHBOARD — point d'entrée
// ══════════════════════════════════════
function updateDashboard(data) {
  const stats        = data.stats || {};
  const transactions = data.transactions || [];

  updateKPIs(stats);
  updateCharts(stats);
  updateTxnTable(transactions);
  updateTopDepenses(stats.top_depenses || []);
  updateBudgetRows(stats.par_categorie || {});
  updateSavings(stats);
}

// ══════════════════════════════════════
//  SYNC SELECTS (mois + personne)
// ══════════════════════════════════════
function syncSelects(mois, personne) {
  ['mois-select','mois-select-txn','mois-select-bud','mois-select-sav'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = mois || '';
  });
  ['personne-select','personne-select-txn','personne-select-bud','personne-select-sav'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = personne || '';
  });
}

// ══════════════════════════════════════
//  CHARGEMENT DONNÉES
// ══════════════════════════════════════
async function loadData(mois, personne) {
  const params = new URLSearchParams();
  if (mois)     params.set('mois', mois);
  if (personne) params.set('personne', personne);
  try {
    const res  = await fetch('/api/dashboard-data?' + params.toString());
    const data = await res.json();
    updateDashboard(data);
    syncSelects(mois, personne);
  } catch (e) {
    console.error('Erreur chargement données:', e);
  }
}

// ══════════════════════════════════════
//  FILTRES MOIS + PERSONNE (async)
// ══════════════════════════════════════
async function applyFilters() {
  const activePage = document.querySelector('.page.active').id;
  let moisId, personneId;
  if (activePage === 'page-transactions') { moisId = 'mois-select-txn'; personneId = 'personne-select-txn'; }
  else if (activePage === 'page-budget')  { moisId = 'mois-select-bud'; personneId = 'personne-select-bud'; }
  else if (activePage === 'page-savings') { moisId = 'mois-select-sav'; personneId = 'personne-select-sav'; }
  else                                    { moisId = 'mois-select';     personneId = 'personne-select'; }

  const mois     = document.getElementById(moisId).value;
  const personne = document.getElementById(personneId).value;
  await loadData(mois, personne);
}

// ══════════════════════════════════════
//  INIT — chargement initial via fetch
// ══════════════════════════════════════
document.addEventListener('DOMContentLoaded', async () => {
  const mois     = document.getElementById('mois-select').value;
  const personne = document.getElementById('personne-select').value;
  await loadData(mois, personne);
});

function toggleBudgetPerson(p, btn) {
  document.querySelectorAll('.person-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
}

// ══════════════════════════════════════
//  RECATEGORISATION IA
// ══════════════════════════════════════
async function recategorizeAI() {
  const btn = document.getElementById('btn-ai');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = '⏳ IA en cours…';

  try {
    const res = await fetch('/api/recategorize-ai', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showDashToast(`✦ ${data.updated} transactions catégorisées par l'IA !`, 'ok');
      setTimeout(() => window.location.reload(), 1500);
    } else {
      showDashToast('Erreur IA', '');
      btn.disabled = false;
      btn.textContent = "✦ Catégoriser avec l'IA";
    }
  } catch(e) {
    showDashToast('Erreur réseau', '');
    btn.disabled = false;
    btn.textContent = "✦ Catégoriser avec l'IA";
  }
}

async function correctDashboard(transactionId, newCategory, selectEl) {
  selectEl.disabled = true;
  try {
    const res = await fetch('/api/correct', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transaction_id: transactionId,
        categorie: newCategory,
        libelle: selectEl.closest('tr').dataset.libelle
      })
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (data.success) {
      const row = selectEl.closest('tr');
      row.dataset.cat = newCategory;
      row.classList.toggle('unknown', newCategory === 'Unknown');
      showDashToast('✓ ' + newCategory + ' — enregistré', 'ok');
    } else {
      showDashToast('Erreur lors de la mise à jour', '');
    }
  } catch(e) {
    showDashToast('Erreur réseau — réessayez', '');
  } finally {
    selectEl.disabled = false;
  }
}

async function correctType(id, type, selectEl) {
  const cat = selectEl.dataset.cat;
  try {
    const res = await fetch('/api/correct', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transaction_id: id, categorie: cat, type_depense: type })
    });
    const data = await res.json();
    if (data.success) showDashToast('✓ Type mis à jour', 'ok');
    else showDashToast('Erreur', '');
  } catch(e) { showDashToast('Erreur réseau', ''); }
}

function showDashToast(msg, type) {
  const t = document.getElementById('dash-toast');
  t.textContent = msg;
  t.className = `show ${type}`;
  setTimeout(() => t.className = '', 2000);
}
