# Adapters nativos de integracoes

Plugin Hermes `ultron_adoption`. Nao e scheduler, proxy ou substituto do Ultron.
Vitrine TikTok Shop permanece bloqueada por decisao do titular. Links afiliados
externos usam o fluxo existente, separado do catalogo nativo Shop.

| Ferramenta | Perfis | Quando usar |
|---|---|---|
| `adoption_status` | Ultron, Mr. Robot, Dona, Maquiavel, Money | Consultar disponibilidade e IDs auditaveis |
| `adoption_skill_audit` | Ultron, Mr. Robot | Antes de recomendar instalar/atualizar skill cadastrada |
| `adoption_caption_import` | Ultron, Dona, Maquiavel | JSON advanced Transcriptonic fornecido pelo titular |
| `adoption_marketing_guide` | Money | Abrir a skill pertinente antes de roteiro/copy/analise de campanha |

Registro de ferramentas e contexto usa APIs nativas do Hermes. O worker recebe
so o toolset permitido ao seu perfil. Nao libera terminal, envio de mensagens,
delegacao, publicacao ou leitura arbitraria para os especialistas.

O Money usa o leitor nativo `skill_view` com `preprocess=False`: templates e
comandos inline nao sao executados. Aceita apenas as dez skills do seu catalogo
instalado e confere a origem efetivamente resolvida. Nao expoe `skill_manage`.
Referencias sao listadas, nao carregadas automaticamente. As dez leituras foram
validadas no perfil real sem chamar modelos nem expor o conteudo em logs.

## Instalacao local

Construa primeiro o scanner conforme `../audit/README.md`. Verifique gateway
ocioso, sem claims/jobs em execucao. Faca backup externo (por exemplo Restic)
antes de parar o gateway. Nao parar um job em andamento para instalar.

```sh
systemctl stop hermes-gateway.service
python agent/integrations/install_local.py --apply \
  --image sha256:ID_COMPLETO_DA_IMAGEM_LOCAL \
  --backup /caminho/privado/backup-novo
systemctl start hermes-gateway.service
```

O operador deve garantir a retomada do servico mesmo se o comando falhar.
Esta migracao e especifica da instalacao auditada em `/root/.hermes`, nao um
instalador generico para outros usuarios ou versoes de worker.
Instalador verifica estado parado, imagem local imutavel e hash conhecido do
worker; nao deve ser forcado contra outra revisao. Gera backup privado antes
de escrever, rejeita alteracoes durante staging e reverte falhas de aplicacao.
Preserva modelos, demais plugins/toolsets, SOULs, cron e contas. A checagem de
hash corresponde ao worker local auditado, nao a todo Hermes upstream.

Helpers de auditoria e importacao sao copiados para dentro do pacote instalado;
o plugin nao depende de `sys.path` da arvore de desenvolvimento. Catalogo e
runtime ficam no home privado. Nunca publicar configuracao real ou transcricoes.

## Transcricao

`adoption_caption_import` recebe JSON (nao URL, arquivo arbitrario ou cookie).
Produz `report-input.json` e `transcript.txt` privados e idempotentes, com hash,
timestamps e rotulos da plataforma. Preserva chat e origem no JSON. Nao afirma
ter transcrito audio; nao verifica identidades nem confirma decisoes/acoes.

O JSON pode alimentar os renderers existentes em `../meeting`. Esta ferramenta
nao envia relatorios, nao instala a extensao no navegador e nao demonstra a
acuracia do ASR. Captura/reprocessamento de audio continuam no pipeline existente.

```sh
python -m pytest agent/integrations agent/audit -q
```
