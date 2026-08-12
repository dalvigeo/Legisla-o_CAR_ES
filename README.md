# Legislação CAR/ES

Catálogo web de normas aplicadas ao Cadastro Ambiental Rural no Espírito Santo, organizado no contexto do projeto **DescompliCAR**.

## Objetivo

Disponibilizar uma fonte de consulta simples para localizar normas federais e estaduais relacionadas a:

- Cadastro Ambiental Rural (CAR)
- Área de Preservação Permanente (APP)
- Reserva Legal
- Programa de Regularização Ambiental (PRA)
- Mata Atlântica e vegetação nativa
- Barragens e reservatórios
- Compensação e regularização ambiental
- Georreferenciamento e registro de imóveis
- Fiscalização ambiental

O projeto é **um catálogo**, não uma publicação oficial nem uma consolidação normativa substitutiva das fontes governamentais.

## Estrutura

- `index.html` — página inicial com catálogo, busca e filtros.
- `norma.html` — ficha individual de cada norma.
- `data.js` — base estruturada das normas cadastradas.
- `app.js` — pesquisa e filtragem.
- `norma.js` — renderização das fichas e relações temáticas.
- `styles.css` — identidade visual e layout responsivo.

## Critério de fontes

São priorizadas fontes oficiais, especialmente:

- Presidência da República / Planalto para legislação federal;
- CONAMA/MMA/ICMBio para atos próprios, quando disponível;
- Governo do Estado do Espírito Santo e Assembleia Legislativa;
- Instituto de Defesa Agropecuária e Florestal do Espírito Santo (Idaf) para normas, instruções e procedimentos de sua competência.

Quando o órgão disponibiliza texto compilado ou consolidado, ele deve ser preferido. Quando a página oficial mantém norma-base e atos alteradores separados, o catálogo indica a necessidade de conferência conjunta.

**Conferência inicial do catálogo: 11/08/2026.**

## Publicação no GitHub Pages

O site não depende de build, framework ou servidor. Para publicar:

1. Abra `Settings` no repositório.
2. Acesse `Pages`.
3. Em `Build and deployment`, escolha `Deploy from a branch`.
4. Selecione a branch `main` e a pasta `/ (root)`.
5. Salve.

## Manutenção

Para cadastrar nova norma, adicione um objeto ao array `window.NORMAS` em `data.js`, informando:

- identificador (`id`);
- esfera;
- tipo;
- número e data;
- situação;
- órgão;
- título e subtítulo;
- descrição curta;
- temas;
- nome da fonte oficial;
- URL da fonte;
- observação, quando necessária.

## Aviso

Antes de utilizar qualquer norma em parecer, laudo, relatório, orientação, decisão administrativa ou manifestação jurídica, confira a íntegra, a vigência e eventuais alterações posteriores diretamente na fonte oficial indicada.
