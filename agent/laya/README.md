# Laya: avaliacao isolada

Instalado localmente em `/root/ultron-local/integrations/laya-eval`.
Nao existe daemon permanente, hook no gateway, acesso a ferramentas ou decisao
de producao. Personalidades e validadores permanecem inalterados.

## Resultado em 02/10/2026

- Pacote `@receptron/laya@0.1.2` instalado com lockfile e `--ignore-scripts`.
- Cinco arquivos ONNX/tokenizer baixados em revisao fixa, conferidos por tamanho
  e SHA-256 LFS ou identidade Git blob; manifesto privado junto ao modelo.
- Tres testes da politica passaram. `npm audit` nao encontrou vulnerabilidades
  conhecidas nas dependencias naquele momento; isso nao equivale a auditoria completa.
- Modelo publicado somente em ingles; a pasta multilingual citada no exemplo
  nao existia no snapshot consultado.
- Teste real interrompido durante carregamento: 73,883 segundos, pico reportado
  de 2 GB, CPU 58,921 segundos. Houve lentidao e timeout de uma chamada ao WSL.
- Nao houve resultado de acuracia ou latencia de inferencia. Portanto, nenhum
  ganho foi demonstrado e a ativacao em producao permanece desabilitada.
- Gateway confirmado ativo e processo de teste confirmado inativo ao encerrar.

## O que ele pode agregar

[Laya](https://github.com/receptron/laya) classifica estado em escolhas, pontuacoes
e probabilidades. Nao gera respostas, nao executa ferramentas e nao substitui
o Hermes ou revisores. O encaixe candidato e triagem curta e local.

O checkpoint trunca entradas; nao deve receber relatorios longos nem decidir
se anexos foram entregues. Probabilidade alta nao prova acuracia em portugues.
O limite de menos de 20 opcoes recomendado pelo upstream tambem impede usar
diretamente os 22 perfis como um unico conjunto de escolhas.

## Reproducao

Copiar os arquivos deste diretorio para um diretorio isolado, executar
`npm ci --ignore-scripts` e `npm test`. O script `download_model.py` baixa os
dados publicos para o caminho local fixo e verifica a integridade.

`benchmark.mjs` exige `LAYA_MODEL_DIR` com o modelo verificado e pelo menos
4 GiB de MemAvailable. Executar somente em processo limitado por cgroup,
fora do gateway. `LAYA_REPORT` define o arquivo JSON de resultados sinteticos.
O teste anterior usou MemoryMax=2300M, MemorySwapMax=0, CPUQuota=150%,
RuntimeMaxSec=180 e Nice=10. Nao remover limites para forcar a conclusao.

Fixture: saudacoes, e-mail com UID/data, SAP explicito, saude, compras, viagens,
assuntos misturados, continuidade e instrucao maliciosa citada. Nenhuma
credencial ou mensagem real e enviada ao modelo.

Antes de ativar: concluir teste local, avaliar portugues em conjunto independente,
medir ganho contra a triagem atual e assegurar folga de memoria. Caso contrario,
manter Hermes. Nao atribuir o benchmark de Apple Silicon do upstream a esta maquina.
