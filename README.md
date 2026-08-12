# Legislação CAR/ES

Base web de normas aplicadas ao Cadastro Ambiental Rural no Espírito Santo, organizada no contexto do projeto **DescompliCAR**.

## Objetivo

Disponibilizar uma fonte de consulta simples para localizar e ler normas federais e estaduais relacionadas a:

- Cadastro Ambiental Rural (CAR)
- Área de Preservação Permanente (APP)
- Reserva Legal
- Programa de Regularização Ambiental (PRA)
- Mata Atlântica e vegetação nativa
- Barragens e reservatórios
- Compensação e regularização ambiental
- Georreferenciamento e registro de imóveis
- Fiscalização ambiental

Cada norma possui uma página de leitura com **texto transcrito e formatado**, identificação da fonte utilizada e link clicável para o documento ou página de origem. O projeto não substitui a publicação oficial.

## Estrutura

- `index.html` — página inicial organizada por esfera.
- `busca.html` — pesquisa por termo, esfera, situação e tema, incluindo o conteúdo das normas.
- `norma.html` — página individual de leitura da norma.
- `data.js` — catálogo e metadados das normas.
- `textos/` — textos formatados gerados para cada norma.
- `generated-index.js` — índice textual utilizado pela busca.
- `generated-sources.js` — fontes efetivamente usadas na transcrição e fontes oficiais.
- `generated-report.json` — relatório da última coleta automática.
- `source_overrides.json` — exceções de fonte e regras de consolidação editorial.
- `scripts/build_legislation.py` — coletor, extrator e formatador dos textos.
- `.github/workflows/atualizar-textos.yml` — atualização automática pelo GitHub Actions.
- `app.js`, `busca.js`, `norma.js` — interface do catálogo, pesquisa e leitura.
- `styles.css` — identidade visual e formatação jurídica.

## Critério de fontes

São priorizadas fontes oficiais, especialmente:

- Presidência da República / Planalto para legislação federal;
- CONAMA/MMA/ICMBio para atos próprios;
- Governo do Estado do Espírito Santo e Assembleia Legislativa;
- Instituto de Defesa Agropecuária e Florestal do Espírito Santo (Idaf) para normas, instruções e procedimentos de sua competência.

Quando existir texto oficial compilado ou consolidado, ele deve ser preferido. Quando a fonte oficial disponibiliza apenas o ato original e suas alterações separadamente, o projeto pode indicar uma fonte de consolidação distinta, mantendo também o acesso à fonte oficial. Essa diferença deve permanecer explícita na página da norma.

## Pesquisa

A pesquisa considera dois grupos de informações com pesos diferentes:

1. **Maior relevância:** título, número, temas, subtítulo e descrição.
2. **Relevância secundária:** ocorrência dos termos no texto integral da norma.

Dessa forma, uma norma cujo assunto principal corresponde à pesquisa tende a aparecer antes de outra em que a expressão aparece apenas incidentalmente em um artigo.

Os filtros e termos pesquisados são mantidos na URL, permitindo compartilhar pesquisas específicas.

## Atualização dos textos

O workflow `Atualizar textos das normas` executa o coletor automaticamente quando a base ou as regras de coleta mudam e também pode ser executado manualmente no GitHub Actions.

O processo:

1. localiza a fonte cadastrada;
2. tenta resolver o arquivo direto quando o cadastro aponta para uma página-lista do Idaf;
3. extrai texto de HTML ou PDF;
4. remove marcações de redações substituídas quando a fonte compilada as apresenta riscadas;
5. formata artigos, parágrafos, incisos e alíneas;
6. grava `textos/<id>.html`;
7. atualiza o índice de busca e o relatório de coleta.

Uma falha de coleta não é preenchida com texto inferido: o sistema registra a ocorrência e mantém o link para a fonte cadastrada até que a origem correta seja resolvida.

## Publicação no GitHub Pages

O site é estático. Em `Settings > Pages`, publique a branch `main` pela pasta `/ (root)`.

## Manutenção

Para cadastrar nova norma, adicione um objeto ao array `window.NORMAS` em `data.js`, informando identificador, esfera, tipo, número, data, situação, órgão, título, descrição, temas e fonte.

Se a norma precisar de uma fonte diferente para extração do texto ou de regra especial de consolidação, registre a exceção em `source_overrides.json`.

## Aviso

As transcrições existem para facilitar consulta e pesquisa. Antes de utilizar qualquer norma em parecer, laudo, relatório, orientação, decisão administrativa ou manifestação jurídica, confira a situação normativa e a publicação oficial. Em caso de divergência, prevalece a fonte oficial.
