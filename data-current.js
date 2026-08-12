// Ajustes de vigência identificados após a criação inicial do catálogo.
// Este arquivo é carregado depois de data.js e também é incorporado pelo gerador.
(function () {
  const normas = window.NORMAS || [];

  const antiga = normas.find(n => n.id === 'in-icmbio-5-2016');
  if (antiga) {
    antiga.status = 'Histórica / revogada';
    antiga.descricao = 'Norma histórica que disciplinava a compensação de Reserva Legal mediante doação de imóveis em unidades de conservação federais. Foi expressamente revogada pela Instrução Normativa ICMBio nº 24/2025.';
    antiga.observacao = 'Revogada pelo art. 42 da Instrução Normativa ICMBio nº 24/2025. Mantida no catálogo para consulta histórica.';
  }

  if (!normas.some(n => n.id === 'in-icmbio-24-2025')) {
    normas.splice(Math.max(0, normas.findIndex(n => n.id === 'in-icmbio-5-2016') + 1), 0, {
      id: 'in-icmbio-24-2025', esfera: 'Federal', tipo: 'Instrução Normativa', numero: 'ICMBio 24/2025', data: '12/08/2025', status: 'Vigente', orgao: 'ICMBio',
      titulo: 'Instrução Normativa ICMBio nº 24, de 12 de agosto de 2025',
      subtitulo: 'Doação de imóveis para compensação de Reserva Legal e outras medidas compensatórias',
      descricao: 'Norma vigente do ICMBio para recebimento de imóveis situados em unidades de conservação federais de domínio público por doação voluntária, antecipada, para compensação de Reserva Legal, compensação florestal e outras medidas compensatórias.',
      temas: ['Reserva Legal', 'Compensação', 'Unidades de conservação', 'Doação', 'Regularização fundiária'],
      fonte: 'Diário Oficial da União — Imprensa Nacional',
      fonteUrl: 'https://www.in.gov.br/en/web/dou/-/instrucao-normativa-icmbio-n-24-de-12-de-agosto-de-2025-648311919',
      observacao: 'Texto vigente com as alterações promovidas pela Instrução Normativa ICMBio nº 16/2026.'
    });
  }

  if (!normas.some(n => n.id === 'in-icmbio-16-2026')) {
    const pos = normas.findIndex(n => n.id === 'in-icmbio-24-2025');
    normas.splice(pos + 1, 0, {
      id: 'in-icmbio-16-2026', esfera: 'Federal', tipo: 'Instrução Normativa', numero: 'ICMBio 16/2026', data: '13/03/2026', status: 'Alteradora', orgao: 'ICMBio',
      titulo: 'Instrução Normativa ICMBio nº 16, de 13 de março de 2026',
      subtitulo: 'Altera a Instrução Normativa ICMBio nº 24/2025',
      descricao: 'Promove alterações no procedimento de doação de imóveis ao ICMBio, inclusive quanto à doação antecipada, responsabilidades do interessado e averbação das destinações como medidas compensatórias.',
      temas: ['Reserva Legal', 'Compensação', 'Unidades de conservação', 'Doação', 'Regularização fundiária'],
      fonte: 'Diário Oficial da União — Imprensa Nacional',
      fonteUrl: 'https://www.in.gov.br/en/web/dou/-/instrucao-normativa-icmbio-n-16-de-13-de-marco-de-2026-693132826'
    });
  }

  window.NORMAS = normas;
})();
