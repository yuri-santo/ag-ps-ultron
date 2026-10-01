# Recriar o Ultron: componentes publicados e limites

Este guia descreve o clone publico, separado da instalacao particular do autor.
Ha uma demonstracao offline de relatorios e instaladores para um Hermes ja
configurado. O repositorio ainda nao recria o agente completo em um comando.

## 1. Codigo e Python

Para o agente local, use Linux ou WSL com Debian/Ubuntu. O painel roda no Windows:
veja [panel/SETUP.md](../panel/SETUP.md). Hermes, Ultron e 9Router desta instalacao
sao locais; VPS finaro nao participa e nao e requisito de nenhum componente.
No PowerShell, se o WSL ainda nao estiver instalado:

```powershell
wsl --install -d Debian
```

Reinicie se solicitado e conclua a criacao do usuario Linux. Dentro da
distribuicao, use Python 3.11 ou superior e Git. Em Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
python3 --version
git clone https://github.com/yuri-santo/ag-ps-ultron.git
cd ag-ps-ultron
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r agent/requirements-report.txt
```

Se o Python da distribuicao for anterior a 3.11, atualize-o antes de criar o
ambiente. As faixas de dependencias nao sao um lockfile; uma instalacao limpa
dessas faixas ainda nao foi validada nesta entrega.

Relatorios tambem rodam no Windows: crie o ambiente com `py -3 -m venv .venv`
e use `.venv\Scripts\python.exe` no lugar de `python`, inclusive no comando
`-m pip install -r agent/requirements-report.txt`. Nao precisa ativar o ambiente.

## 2. Demonstracao offline: JSON, PDF e DOCX

Na raiz do clone, depois de preparar as dependencias:

```bash
python agent/meeting/import_transcriptonic.py agent/meeting/examples/transcriptonic.json --output meeting.json
python agent/meeting/render_report.py meeting.json ata.pdf
python agent/meeting/render_docx.py meeting.json ata.docx
```

O exemplo e sintetico. O importador recebe o JSON do webhook avancado do
Transcriptonic salvo em disco; nao captura reunioes, instala extensoes ou chama
IA. Ele recusa sobrescrever `meeting.json`: para repetir, escolha outro caminho.
Os renderizadores podem substituir os arquivos de saida.

O resultado preserva falas, horarios e origem. Nomes da plataforma sao rotulos,
nao identidades verificadas. O chat fica separado das falas no JSON. O importador
nao transforma frases automaticamente em decisoes ou tarefas confirmadas;
`records` comeca vazio. A demo comprova importacao e geracao de documentos,
nao analise semantica completa nem entrega pelo Telegram.

PDF usa ReportLab; DOCX usa python-docx e Pillow e o modulo compartilhado de atas.
PyMuPDF serve para inspecao/verificacao de PDFs.

## 3. Hermes local: requisito externo

O [dashboard financeiro](../finance-dashboard/README.md) tambem pode ser
executado separadamente, com base ficticia ou vazia e senha propria.
Ele nao depende de copiar o banco financeiro pessoal do autor.

Instale e configure o [Hermes Agent](https://github.com/NousResearch/hermes-agent)
seguindo a documentacao oficial da versao escolhida. Configure provedor de modelo
e canal de mensagens e confirme o funcionamento antes de adicionar plugins.
Registre a versao instalada: este repositorio nao fixa uma revisao do Hermes
nem valida todas as versoes da API de plugins.

9Router e uma opcao de gateway de modelos; nao e dependencia da demo offline.
O [INSTALL.md](../INSTALL.md) conserva exemplos legados de VPS, que nao
descrevem a instalacao deste Hermes. Nao os use para configurar o bot local.

O diretorio de dados do Hermes deve conter `config.yaml`. Normalmente e
`~/.hermes` para o usuario do agente; `/root/.hermes` corresponde a execucao como
root. Nao copie arquivos privados do autor.

## 4. Instalar somente o Ultron Lab

O Lab usa `agent/plugins/ultron_lab`, skills e inventarios publicados. Ele nao
cria os especialistas nem instala o Hermes. Requer PyYAML:

```bash
python -m pip install 'PyYAML>=6,<7'
python agent/deploy_lab.py stage --home ~/.hermes --cenario pc --dry-run
```

Troque `~/.hermes` pelo diretorio real do agente em todos os comandos. Use
`--cenario servidor` para o outro inventario. `--dry-run` lista o plano sem
gravar arquivos; nao comprova integracoes externas. Apos conferir o plano:

```bash
python agent/deploy_lab.py stage --home ~/.hermes --cenario pc
python agent/deploy_lab.py activate --home ~/.hermes --dry-run
python agent/deploy_lab.py activate --home ~/.hermes
```

`stage` copia plugin, skills e inventario, com backup de destinos gerenciados.
`activate` altera `config.yaml` para habilitar o plugin. A simulacao de activate
requer um stage existente. Nenhuma etapa reinicia o gateway. Reinicie pelo
procedimento da sua instalacao e confira logs e ferramentas carregadas.
Esses comandos nao foram executados no agente real nesta entrega; os testes
usam diretorios temporarios.

O Lab preserva arquivos SOUL. Perfis de e-mail `gmail` e `easysapers` sao
opcionais; quando existentes, recebem a integracao. Isso nao instala contas,
scripts externos nem credenciais. Ajuste o inventario de servicos antes de
interpretar o monitoramento. O instalador nao sobe containers.

### Team legado: modifica personalidade

**Nao execute `agent/deploy.py stage` ou `activate` para preservar a personalidade.**
Stage regrava SOUL/config dos perfis gerenciados; activate acrescenta conteudo ao
SOUL principal e tenta adaptar um `meeting_copilot` preexistente. O script fixa
`/root/.hermes` e exige `bigode`, `thor` e `hercules` preexistentes. Corrigir seus
caminhos de fontes nao o torna um bootstrap de maquina nova. Essas etapas nao
foram executadas na instalacao real nesta entrega.

## 5. Transcricao e diarizacao opcionais

```bash
python -m pip install -r agent/requirements-stt.txt
python agent/stt/parakeet_cli.py --help
python agent/stt/diarizar.py --help
```

Esses requisitos sao separados dos relatorios. Wheels e compatibilidade dependem
do Python, sistema e arquitetura. A resolucao dessas faixas e o reconhecimento
com modelos reais nao foram testados nesta entrega. Modelos nao acompanham o
repositorio: obtenha-os separadamente e registre origem, versao, licenca e checksum.

| Modulo | Variavel | Arquivos externos esperados |
| --- | --- | --- |
| Parakeet | `ULTRON_PARAKEET_DIR` | `encoder*.onnx`, `decoder*.onnx`, `joiner*.onnx`, `tokens.txt`, de um mesmo modelo compativel |
| Diarizacao | `ULTRON_STT_MODELS` | `seg/**/model*.onnx` de segmentacao e `emb.onnx` de embeddings compativeis com sherpa-onnx |

Sem essas variaveis, os padroes sao `/root/tools/stt-models/parakeet` e
`/root/tools/stt-models`. Configure os caminhos da sua maquina:

```bash
export ULTRON_PARAKEET_DIR=$HOME/ultron-models/parakeet
export ULTRON_STT_MODELS=$HOME/ultron-models
mkdir -p transcricao
python agent/stt/parakeet_cli.py --input reuniao.wav --output-dir transcricao --language pt
```

O ultimo comando exige audio e modelos reais. `--language` integra a interface
do adaptador, mas o codigo atual nao o usa para configurar o reconhecedor.
O modelo escolhido precisa cobrir o idioma desejado. Captura de microfone e
loopback, consolidacao e envio dependem do runtime externo; o CLI nao configura
esse encadeamento.

## 6. O que falta para recriar a instalacao completa

| Componente | Estado do clone | Requisitos adicionais |
| --- | --- | --- |
| PDF/DOCX e importador | Codigo e exemplo publicados | Dependencias Python e dados de entrada |
| STT e diarizacao | Adaptadores publicados | Modelos, captura e validacao por idioma |
| `meeting_copilot` | Referenciado; implementacao completa ausente | Plugin, banco/esquema e captura/consolidacao |
| Calendario | Dependencias externas referenciadas | `calendar_bridge.py`, `/root/tools/cal_daily2.py`, ambiente e contas |
| E-mail | Ferramentas consumidoras publicadas | Scripts email-manager, contas locais e autenticacao |
| Especialistas | Descricao em AGENTS.md; poucos perfis de exemplo | Criar demais perfis, ferramentas e configuracao sem dados privados |
| Personalidade e memoria | SOULs privados nao publicados | Identidade e memoria proprias; preservar as do agente existente |
| Homelab | Compose, cenarios e inventarios publicados | Docker, volumes, segredos e recursos; ver `agent/homelab/README.md` |
| Painel Windows | Codigo publicado | Pasta completa, apps e endpoints; ver `panel/SETUP.md` |
| Autostart e scripts historicos | Varios caminhos pessoais fixos | Adaptacao e verificacao antes de executar `agent/scripts/` |

`agent/scripts/instalar-ultron-lab.sh` nao e instalador universal: tem caminhos
historicos, stacks removidos e servicos systemd particulares. Credenciais,
bancos reais e SOULs privados nao devem ser publicados para preencher essas lacunas.

## 7. Evidencia e limites da verificacao

Testes de instalacao usam um Hermes sintetico e arquivos reais do clone; nao
demonstram um gateway funcional. A demo offline foi verificada no Windows com
ReportLab 5.0.1, python-docx 1.2.0, Pillow 12.3.0 e PyMuPDF 1.28.2 ja instalados.
Nao foram instalados pacotes, baixados modelos ou criadas contas nessa verificacao.

Uma instalacao completa ainda precisa validar no ambiente alvo: carregamento
dos plugins, captura real, qualidade da transcricao PT-BR, identificacao
conservadora de falantes, rastreabilidade das decisoes e entrega no canal
configurado. Renderizacao local nao comprova essas etapas.
