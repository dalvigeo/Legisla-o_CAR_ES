const normas = window.NORMAS || [];
const sourceMap = window.NORM_SOURCES || {};
const params = new URLSearchParams(location.search);
const normaId = params.get('id');
const norma = normas.find(item => item.id === normaId);
const content = document.getElementById('normaContent');
const breadcrumbTitle = document.getElementById('breadcrumbTitle');

function statusClass(status) {
  if (status === 'Vigente') return 'status-vigente';
  if (status === 'Alteradora') return 'status-alteradora';
  return 'status-historica';
}

function relatedNormas(current) {
  const themes = new Set(current.temas || []);
  return normas
    .filter(item => item.id !== current.id)
    .map(item => ({
      item,
      score: (item.temas || []).reduce((total, theme) => total + (themes.has(theme) ? 1 : 0), 0)
    }))
    .filter(entry => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.item.titulo.localeCompare(b.item.titulo, 'pt-BR'))
    .slice(0, 6)
    .map(entry => entry.item);
}

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

async function loadNormText(id, officialUrl) {
  const target = document.getElementById('textoNorma');
  try {
    const response = await fetch(`textos/${encodeURIComponent(id)}.html`, { cache: 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    target.innerHTML = await response.text();

    if (location.hash) {
      requestAnimationFrame(() => {
        const element = document.getElementById(location.hash.slice(1));
        if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  } catch (error) {
    target.innerHTML = `
      <div class="notice">
        <strong>Não foi possível carregar a transcrição desta norma.</strong>
        Consulte a fonte cadastrada enquanto o conteúdo é atualizado.
      </div>
      <p><a class="source-link primary" href="${escapeHtml(officialUrl)}" target="_blank" rel="noopener">Acessar fonte ↗</a></p>`;
  }
}

if (!norma) {
  document.title = 'Norma não encontrada | Legislação CAR/ES';
  content.innerHTML = `
    <div class="info-card">
      <h1>Norma não encontrada</h1>
      <p>O identificador informado não existe no catálogo atual.</p>
      <a class="source-link primary" href="index.html">Voltar ao catálogo</a>
    </div>`;
} else {
  const source = sourceMap[norma.id] || {};
  const officialUrl = source.officialUrl || norma.fonteUrl;
  const textSourceUrl = source.textSourceUrl || officialUrl;
  const textSourceLabel = source.textSourceLabel || norma.fonte || 'Fonte utilizada';
  const sameSource = officialUrl === textSourceUrl;

  document.title = `${norma.titulo} | Legislação CAR/ES`;
  breadcrumbTitle.textContent = norma.titulo;

  const tags = (norma.temas || []).map(theme => `<span class="tag">${theme}</span>`).join('');
  const related = relatedNormas(norma);
  const relatedHtml = related.length
    ? related.map(item => `
      <a class="related-item" href="norma.html?id=${encodeURIComponent(item.id)}">
        <strong>${item.titulo}</strong><br>
        <small>${item.subtitulo}</small>
      </a>`).join('')
    : '<p>Nenhuma norma relacionada cadastrada nesta versão.</p>';

  const sourceButtons = `
    <a class="source-link primary" href="${escapeHtml(textSourceUrl)}" target="_blank" rel="noopener">Fonte do texto ↗</a>
    ${!sameSource ? `<a class="source-link" href="${escapeHtml(officialUrl)}" target="_blank" rel="noopener">Fonte oficial ↗</a>` : ''}
    <a class="source-link" href="busca.html?q=${encodeURIComponent((norma.temas || [])[0] || norma.numero)}">Pesquisar relacionadas</a>`;

  content.innerHTML = `
    <article class="norma-header norma-header-compact">
      <div class="card-top">
        <span class="card-type">${norma.esfera} · ${norma.tipo}</span>
        <span class="status-badge ${statusClass(norma.status)}">${norma.status}</span>
      </div>
      <h1>${norma.titulo}</h1>
      <p class="norma-description"><strong>${norma.subtitulo}</strong></p>
      <p class="norma-description">${norma.descricao}</p>

      <div class="norma-meta norma-meta-compact">
        <div class="meta-box"><span class="meta-label">Número</span><span class="meta-value">${norma.numero}</span></div>
        <div class="meta-box"><span class="meta-label">Data</span><span class="meta-value">${norma.data}</span></div>
        <div class="meta-box"><span class="meta-label">Órgão</span><span class="meta-value">${norma.orgao}</span></div>
        <div class="meta-box"><span class="meta-label">Fonte da transcrição</span><span class="meta-value">${escapeHtml(textSourceLabel)}</span></div>
      </div>

      <div class="tags">${tags}</div>
      <div class="norma-actions">${sourceButtons}</div>
      ${source.note ? `<div class="source-note">${escapeHtml(source.note)}</div>` : ''}
    </article>

    <section class="norm-text-card">
      <div id="textoNorma" class="text-loading">Carregando texto da norma…</div>
    </section>

    <section class="related-section">
      <div class="section-heading">
        <div><span class="section-kicker">NAVEGAÇÃO</span><h2>Normas relacionadas</h2></div>
      </div>
      <div class="related-list related-grid">${relatedHtml}</div>
    </section>`;

  loadNormText(norma.id, officialUrl);
}
