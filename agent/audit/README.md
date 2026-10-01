# Auditoria isolada de skills

SkillSpector foi adotado como scanner, nao como aprovador nem outro agente.
Fonte: [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector), commit
`2226747e4ca97198bb82faf5085b8a75f2e1dc02`, Apache-2.0.

## Construir

Use Docker Linux, Git e uv 0.12.17. Clone com `gh repo clone NVIDIA/SkillSpector`
e confira o commit antes de construir. O contexto de build deve conter:

1. Este `Dockerfile`.
2. Binario Linux `uv`, SHA256
   `553a67a24d306a803d5c45678b7c54ed0c8b698d9fe3835d54905811348ccf2a`.
3. Pasta `source` extraida de `git archive` do commit acima, nunca da arvore suja.
   O SHA256 do arquivo tar observado e
   `95de8910f7b9b43bb9dc244af99a46361192d2b10ff69c048e280384282a0812`.

```sh
docker build -t ultron-skillspector:2226747 /caminho/do/contexto
docker image inspect ultron-skillspector:2226747 --format '{{.Id}}'
```

O build usa rede para instalar as dependencias do `uv.lock` congelado; scans nao.
O Dockerfile fixa a imagem Python 3.13 por digest. Hermes continua no Python 3.11.
Nao substituir a imagem do scanner por `latest` na configuracao.

## Executar pelo Hermes

O plugin em `../integrations` fornece `adoption_skill_audit(skill=ID)` ao Ultron
e Mr. Robot. IDs vem de `adoption_status`, nao de um caminho enviado pelo modelo.
Uma copia dos arquivos e hasheada; links, arquivos especiais e nomes
potencialmente secretos sao recusados. Somente essa copia entra no container.

- Docker local, sem pull, sem rede, sem socket montado, usuario 65534.
- Filesystem readonly, sem capabilities, no-new-privileges, 1 CPU e 1 GiB.
- Snapshot limitado a 20 MiB/2000 arquivos; tempo 120 s; leitura de report 8 MiB.
- Relatorio privado 0600; nenhum texto da skill entra em mensagens de erro.
- `approved` e sempre `false`. Zero alertas nao e certificacao de seguranca.

`--no-llm` e bloqueio de rede retiram analise semantica, consultas remotas e
cobertura transitiva. Referencias ausentes ou analise parcial produzem
`needs_review`, inclusive com zero alertas. Conferir `analysis_complete`.
O limite de leitura nao e uma quota de disco do stdout/stderr temporario.

Teste real em 01/10/2026: skill copywriting instalada foi examinada sem rede;
scanner retornou cobertura parcial por referencia externa ausente. Isso e uma
pendencia de cobertura, nao prova de conteudo malicioso nem aprovacao.

```sh
python -m pytest agent/audit agent/integrations -q
```
