const normas = window.NORMAS || [];
const textIndex = new Map((window.NORM_TEXT_INDEX || []).map(item => [item.id, item.text || '']));

const searchResults = document.getElementById('searchResults');
const searchInput = document.getElementById('searchInput');
const sphereFilter = document.getElementById('sphereFilter');
const statusFilter = document.getElementById('statusFilter');
const themeFilter = document.getElementById('themeFilter');
const clearSearch = document.getElementById('clearSearch');
const resultCount = document.getElementById('resultCount');
const emptyState = document.getElementById('emptyState');

function normalizeText(value = '') {
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[º°ª]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function statusClass(status) {
  if (status === 'Vigente') return 'status-vigente';
  if (status === 'Alteradora') return 'status-alteradora';
  return 'status-historica';
}

function fieldsFor(norma) {
  return {
    titulo: normalizeText(norma.titulo),
    numero: normalizeText(norma.numero),
    temas: normalizeText((norma.temas || []).join(' ')),
    subtitulo: normalizeText(norma.subtitulo),
    descricao: normalizeText(norma.descricao),
    orgao: normalizeText(norma.orgao),
    observacao: normalizeText(norma.observacao || ''),
    texto: normalizeText(textIndex.get(norma.id) || '')
  };
}

function scoreNorma(norma, terms, phrase) {
  if (!terms.length) return { score: 0, fields: fieldsFor(norma) };
  const fields = fieldsFor(norma);
  const weights = {
    titulo: 32,
    numero: 32,
    temas: 26,
    subtitulo: 18,
    descricao: 10,
    orgao: 6,
    observacao: 4,
    texto: 1
  };
  let score = 0;
  for (const term of terms) {
    let found = false;
    for (const [field, value] of Object.entries(fields)) {
      if (value.includes(term)) {
        found = true;
        score += weights[field];
        if (value === term) score += weights[field] * 0.5;
      }
    }
    if (!found) return null;
  }
  if (phrase) {
    if (fields.titulo.includes(phrase) || fields.numero.includes(phrase)) score += 45;
    else if (fields.temas.includes(phrase) || fields.subtitulo.includes(phrase)) score += 25;
    else if (fields.descricao.includes(phrase)) score += 10;
    else if (fields.texto.includes(phrase)) score += 2;
  }
  return { score, fields };
}

function makeSnippet(norma, rawQuery) {
  const rawText = textIndex.get(norma.id) || '';
  if (!rawText || !rawQuery.trim()) return '';
  const normalizedQuery = normalizeText(rawQuery);
  const terms = normalizedQuery.split(' ').filter(Boolean);
  const rawLower = rawText.toLocaleLowerCase('pt-BR');
  let position = -1;
  for (const term of terms) {
    const pos = normalizeText(rawText).indexOf(term);
    if (pos >= 0) {
      // A posição normalizada não é idêntica à original; aproximamos buscando a palavra sem acento quando possível.
      const direct = rawLower.indexOf(term);
      position = direct >= 0 ? direct : Math.min(pos, rawText.length - 1);
      break;
    }
  }
  if (position < 0) return '';
  const start = Math.max(0, position - 120);
  const end = Math.min(rawText.length, position + 260);
  let snippet = rawText.slice(start, end).replace(/\s+/g, ' ').trim();
  if (start > 0) snippet = '…' + snippet;
  if (end < rawText.length) snippet += '…';
  return escapeHtml(snippet);
}

function cardTemplate(entry, rawQuery) {
  const norma = entry.norma;
  const tags = (norma.temas || []).slice(0, 6).map(t => `<span class="tag">${t}</span>`).join('');
  const snippet = makeSnippet(norma, rawQuery);
  return `
    <article class="card search-result-card">
      <div class="card-top">
        <span class="card-type">${norma.esfera} · ${norma.tipo}</span>
        <span class="status-badge ${statusClass(norma.status)}">${norma.status}</span>
      </div>
      <h3>${norma.titulo}</h3>
      <p><strong>${norma.subtitulo}</strong></p>
      <p>${norma.descricao}</p>
      ${snippet ? `<div class="search-snippet"><span>Ocorrência no texto:</span>${snippet}</div>` : ''}
      <div class="tags">${tags}</div>
      <div class="card-actions">
        <a class="card-link" href="norma.html?id=${encodeURIComponent(norma.id)}">Abrir texto da norma →</a>
      </div>
    </article>`;
}

function populateThemes() {
  const themes = [...new Set(normas.flatMap(n => n.temas || []))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  themes.forEach(theme => {
    const option = document.createElement('option');
    option.value = theme;
    option.textContent = theme;
    themeFilter.appendChild(option);
  });
}

function getFiltered() {
  const rawQuery = searchInput.value;
  const query = normalizeText(rawQuery);
  const terms = query.split(' ').filter(Boolean);
  const sphere = sphereFilter.value;
  const status = statusFilter.value;
  const theme = themeFilter.value;

  return normas
    .filter(norma => {
      if (sphere && norma.esfera !== sphere) return false;
      if (status && norma.status !== status) return false;
      if (theme && !(norma.temas || []).includes(theme)) return false;
      return true;
    })
    .map(norma => {
      const scored = scoreNorma(norma, terms, query);
      return scored ? { norma, score: scored.score } : null;
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score || a.norma.titulo.localeCompare(b.norma.titulo, 'pt-BR'));
}

function syncUrl() {
  const params = new URLSearchParams();
  if (searchInput.value) params.set('q', searchInput.value);
  if (sphereFilter.value) params.set('esfera', sphereFilter.value);
  if (statusFilter.value) params.set('situacao', statusFilter.value);
  if (themeFilter.value) params.set('tema', themeFilter.value);
  const suffix = params.toString();
  history.replaceState(null, '', suffix ? `?${suffix}` : location.pathname);
}

function render() {
  const filtered = getFiltered();
  searchResults.innerHTML = filtered.map(entry => cardTemplate(entry, searchInput.value)).join('');
  emptyState.hidden = filtered.length !== 0;
  resultCount.textContent = `${filtered.length} de ${normas.length} normas encontradas`;
  syncUrl();
}

function restoreFromUrl() {
  const params = new URLSearchParams(location.search);
  searchInput.value = params.get('q') || '';
  sphereFilter.value = params.get('esfera') || '';
  statusFilter.value = params.get('situacao') || '';
  themeFilter.value = params.get('tema') || '';
}

[searchInput, sphereFilter, statusFilter, themeFilter].forEach(element => {
  element.addEventListener(element === searchInput ? 'input' : 'change', render);
});

clearSearch.addEventListener('click', () => {
  searchInput.value = '';
  sphereFilter.value = '';
  statusFilter.value = '';
  themeFilter.value = '';
  render();
  searchInput.focus();
});

populateThemes();
restoreFromUrl();
render();
