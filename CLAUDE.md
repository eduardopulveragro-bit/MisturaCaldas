# MisturaCaldas — Regras para o Assistente

## Segurança — IMUTÁVEL

- O assistente SUGERE; o agrônomo APROVA. Nada técnico sai como decisão do bot.
- NÃO implementar compatibilidade de calda, verificação de dose contra bula, nem recomendação nova.
- NÃO enviar nome de pessoa, telefone ou fazenda identificável a nenhuma API externa.
  Se encontrar dados pessoais, parar imediatamente e avisar o usuário.
- Registrar em log CADA chamada à API de IA: tokens, custo estimado, ID da chamada.
- A IA extrai itens da mensagem. A ORDEM é decidida por código — nunca por IA.

## Regras de código

- Testes ANTES do código. Cada linha de `pares.csv` é um caso de teste.
- Divergências são LISTADAS para revisão com o especialista — não são corrigidas nas regras.
- Passos pequenos: rodar testes a cada mudança.
- Código comentado em português.
- Chave da API somente em variável de ambiente (`ANTHROPIC_API_KEY`); nunca hardcoded.

## Estrutura

```
data/
  regras_ordem.csv   — 20 posições (fonte da verdade para ordenação)
  produtos.csv       — cadastro de produtos (chave: registro_mapa)
  pares.csv          — pares para teste de ordenação
  pontas.csv         — tabela de ponta × pressão × vazão
  fazendas/*.json    — dados de cada fazenda/máquina
src/
  parser.py          — ÚNICO ponto de contato com IA (extração)
  ordenacao.py       — ordenação sem IA
  calculo.py         — fórmula L/ha (fixa, sem IA)
  pontas.py          — sugestão de ponta (sem IA)
  pdf_gen.py         — geração do PDF
tests/
  test_ordenacao.py  — suite baseada em pares.csv
app.py               — Flask na porta 3002
logs/app.log         — log de chamadas de IA
```

## Fórmula de taxa

```
L/ha = vazão(L/min) × 600 / (velocidade km/h × faixa m)
```

## Produto não cadastrado

Marcar como `pendente: formulação não cadastrada`.
Para buscar na bula do fabricante: mostrar trecho + link, gravar em produtos.csv
**somente após confirmação manual**.
