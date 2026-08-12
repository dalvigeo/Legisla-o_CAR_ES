const normas = window.NORMAS || [];
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

if (!norma) {
  document.title = 'Norma não encontrada | Legislação CAR/ES';
  content.innerHTML = `
    <div class="info-card">
      <h1>Norma não encontrada</h1>
      <p>O identificador informado não existe no catálogo atual.</p>
      <a class="source-link primary" href="index.html">Voltar ao catálogo</a>
    </div>`;
} else {
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

  content.innerHTML = `
    <article class="norma-header">
      <div class="card-top">
        <span class="card-type">${norma.esfera} · ${norma.tipo}</span>
        <span class="status-badge ${statusClass(norma.status)}">${norma.status}</span>
      </div>
      <h1>${norma.titulo}</h1>
      <p class="norma-description"><strong>${norma.subtitulo}</strong></p>
      <p class="norma-description">${norma.descricao}</p>

      <div class="norma-meta">
        <div class="meta-box">
          <span class="meta-label">Número</span>
          <span class="meta-value">${norma.numero}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">Data</span>
          <span class="meta-value">${norma.data}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">Órgão</span>
          <span class="meta-value">${norma.orgao}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">Situação no catálogo</span>
          <span class="meta-value">${norma.status}</span>
        </div>
      </div>

      <div class="tags">${tags}</div>
      <div class="norma-actions" style="margin-top:20px">
        <a class="source-link primary" href="${norma.fonteUrl}" target="_blank" rel="noopener">Acessar fonte oficial ↗</a>
        <a class="source-link" href="busca.html?q=${encodeURIComponent((norma.temas || [])[0] || norma.numero)}">Pesquisar normas relacionadas</a>
      </div>
    </article>

    <div class="info-grid">
      <section class="info-card">
        <h2>Fonte e conferência</h2>
        <p><strong>${norma.fonte}</strong></p>
        ${norma.observacao ? `<p>${norma.observacao}</p>` : ''}
        <div class="notice">
          O Legislação CAR/ES não substitui a publicação oficial. O catálogo serve para localizar normas e seus temas. Para aplicação técnica ou jurídica, confirme a íntegra, alterações posteriores, revogações e vigência diretamente na fonte oficial.
        </div>
      </section>

      <aside class="info-card">
        <h2>Normas relacionadas</h2>
        <div class="related-list">${relatedHtml}</div>
      </aside>
    </div>`;
}
