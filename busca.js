const normas = window.NORMAS || [];

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

function searchableText(norma) {
  return normalizeText([
    norma.titulo,
    norma.subtitulo,
    norma.descricao,
    norma.tipo,
    norma.numero,
    norma.orgao,
    norma.status,
    ...(norma.temas || []),
    norma.observacao || ''
  ].join(' '));
}

function statusClass(status) {
  if (status === 'Vigente') return 'status-vigente';
  if (status === 'Alteradora') return 'status-alteradora';
  return 'status-historica';
}

function cardTemplate(norma) {
  const tags = (norma.temas || []).slice(0, 6).map(t => `<span class="tag">${t}</span>`).join('');
  return `
    <article class="card">
      <div class="card-top">
        <span class="card-type">${norma.esfera} · ${norma.tipo}</span>
        <span class="status-badge ${statusClass(norma.status)}">${norma.status}</span>
      </div>
      <h3>${norma.titulo}</h3>
      <p><strong>${norma.subtitulo}</strong></p>
      <p>${norma.descricao}</p>
      <div class="tags">${tags}</div>
      <div class="card-actions">
        <a class="card-link" href="norma.html?id=${encodeURIComponent(norma.id)}">Consultar ficha →</a>
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
  const query = normalizeText(searchInput.value);
  const terms = query.split(' ').filter(Boolean);
  const sphere = sphereFilter.value;
  const status = statusFilter.value;
  const theme = themeFilter.value;

  return normas.filter(norma => {
    if (sphere && norma.esfera !== sphere) return false;
    if (status && norma.status !== status) return false;
    if (theme && !(norma.temas || []).includes(theme)) return false;
    if (terms.length) {
      const haystack = searchableText(norma);
      if (!terms.every(term => haystack.includes(term))) return false;
    }
    return true;
  });
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
  searchResults.innerHTML = filtered.map(cardTemplate).join('');
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
