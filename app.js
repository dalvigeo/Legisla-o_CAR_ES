const normas = window.NORMAS || [];
const federalGrid = document.getElementById('federalGrid');
const estadualGrid = document.getElementById('estadualGrid');
const federalCount = document.getElementById('federalCount');
const estadualCount = document.getElementById('estadualCount');
const resultCount = document.getElementById('resultCount');

function statusClass(status) {
  if (status === 'Vigente') return 'status-vigente';
  if (status === 'Alteradora') return 'status-alteradora';
  return 'status-historica';
}

function cardTemplate(norma) {
  const tags = (norma.temas || []).slice(0, 5).map(t => `<span class="tag">${t}</span>`).join('');
  const href = `norma.html?id=${encodeURIComponent(norma.id)}`;
  return `
    <a class="card card-clickable" href="${href}" aria-label="Acessar ${norma.titulo}">
      <div class="card-top">
        <span class="card-type">${norma.tipo}</span>
        <span class="status-badge ${statusClass(norma.status)}">${norma.status}</span>
      </div>
      <h3>${norma.titulo}</h3>
      <p><strong>${norma.subtitulo}</strong></p>
      <p>${norma.descricao}</p>
      <div class="tags">${tags}</div>
      <div class="card-actions"><span class="card-link">Acessar texto da norma →</span></div>
    </a>`;
}

const federais = normas.filter(n => n.esfera === 'Federal');
const estaduais = normas.filter(n => n.esfera === 'Estadual');

federalGrid.innerHTML = federais.map(cardTemplate).join('');
estadualGrid.innerHTML = estaduais.map(cardTemplate).join('');
federalCount.textContent = `${federais.length} normas`;
estadualCount.textContent = `${estaduais.length} normas`;
resultCount.textContent = `${normas.length} normas catalogadas nesta versão`;
