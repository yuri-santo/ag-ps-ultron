# Manual de instalação — construindo o seu Ag-PS-Ultron

Passo a passo para instalar e configurar cada peça do zero: o Hermes
Agent (o "Ultron"), o 9Router, as ferramentas de SAP/rede, e o painel
físico. Os comandos abaixo são os reais usados para montar este sistema
— troque hosts/tokens/IDs pelos seus.

## Pré-requisitos

- Uma VPS Linux (Ubuntu/Debian) com Docker instalado — é onde o Hermes e
  o 9Router rodam 24/7.
- Um notebook Windows na mesma rede do painel físico (para o `panel/`),
  com WSL + uma distro Linux (Kali ou outra) para as ferramentas de rede.
- Acesso SSH à VPS configurado com chave (sem senha), via um alias no
  `~/.ssh/config` do notebook.
- Uma conta de bot no Telegram (fale com [@BotFather](https://t.me/BotFather)
  para gerar um token) — ou outro canal de mensageria suportado.

## 1. 9Router — gateway de IA próprio

O 9Router roda como container Docker (imagem `decolua/9router`), com um
volume próprio para persistir configuração/dados:

```bash
docker run -d \
  --name 9router \
  --restart unless-stopped \
  -p 20128:20128 \
  -v /root/.9router:/app/data \
  decolua/9router:latest
```

Depois de subir, configure os provedores de modelo (Gemini, Claude,
OpenRouter etc.) pela interface/API do próprio 9Router — a chave de
runtime gerada é o que os outros componentes (Hermes) vão usar como
"Custom endpoint" compatível com a API da OpenAI.

Teste rápido (uma resposta 401 sem chave já confirma que está no ar):

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:20128/v1/models
```

## 2. Hermes Agent — o agente em si

O Hermes é distribuído como pacote Python (`hermes-agent`) e gerenciado
com [`uv`](https://docs.astral.sh/uv/) (instalador/gerenciador de
ambientes Python rápido):

```bash
# instalar o uv, se ainda não tiver
curl -LsSf https://astral.sh/uv/install.sh | sh

# instalar o hermes-agent como ferramenta isolada (próprio venv)
uv tool install hermes-agent

# confirmar
hermes --version
```

### Configurar o modelo (via 9Router)

```bash
hermes model
# no wizard interativo, escolha "Custom endpoint" e aponte para:
#   URL base:  http://127.0.0.1:20128/v1   (ou o endereço do seu 9Router)
#   Chave:     a chave de runtime gerada pelo 9Router
#   Modelo:    ag/<modelo-desejado>  (ex: ag/gemini-3.7-flash-high)
```

### Conectar ao Telegram — passo a passo completo

1. **Criar o bot**: abra uma conversa com [@BotFather](https://t.me/BotFather)
   no Telegram e mande `/newbot`. Escolha um nome de exibição e um
   username terminado em `bot` (ex: `MeuAgentePessoal_bot`). O BotFather
   devolve um **token** (formato `123456789:ABC-...`) — isso é uma
   credencial, trate como senha.
2. **Descobrir o seu chat id**: mande qualquer mensagem para o bot recém
   criado, depois acesse
   `https://api.telegram.org/bot<TOKEN>/getUpdates` no navegador — o
   campo `"chat":{"id": ...}` da resposta é o seu chat id numérico.
3. **Rodar o assistente do Hermes**:
   ```bash
   hermes setup
   # escolha "Telegram" na lista de plataformas
   # cole o token do BotFather quando pedido
   # informe o chat id (ou deixe o wizard descobrir no primeiro contato)
   ```
4. **Subir o gateway e testar**:
   ```bash
   hermes gateway start
   ```
   Mande uma mensagem de teste para o bot no Telegram — a resposta deve
   vir do agente (usando o modelo configurado no passo anterior, via
   9Router).
5. **Confirmar no status**:
   ```bash
   hermes status
   # -> Messaging Platforms: Telegram ✓ configured
   # -> Gateway Service: Status ✓ running
   ```
6. **(Opcional) Enviar mensagens do lado de fora do chat** — usado pelo
   painel físico e por scripts/cron para notificar proativamente:
   ```bash
   hermes send --to telegram "mensagem de teste"
   ```

**Nunca** commite o token do bot nem o chat id em nenhum repositório —
guarde com `hermes secrets` ou como variável de ambiente local.

### Configurar segredos (recomendado, em vez de variáveis de ambiente soltas)

```bash
hermes secrets
# integra com Bitwarden ou 1Password — credenciais de sites, tokens de
# API etc. ficam no cofre, não em texto puro em arquivos de config
```

### Subir o gateway como serviço permanente

```bash
hermes gateway start
hermes status
# confirma: Gateway Service -> running, Telegram -> configured
```

Para manter rodando 24/7 mesmo depois de reiniciar a VPS, gerencie o
processo do gateway com Docker/systemd/pm2 conforme sua preferência — o
`hermes status` sempre mostra o estado real, independente de como ele
foi mantido de pé.

## 3. Ferramentas próprias (SAP, controle de TV/rede)

Um projetinho Node.js simples ao lado do Hermes, na VPS:

```bash
mkdir -p ~/minhas-ferramentas && cd ~/minhas-ferramentas
npm init -y
npm install playwright   # ou puppeteer, para automação com login persistido
```

- **Controle de TV/rede** (`lg-control.mjs`): um script que fala o
  protocolo de controle das TVs LG na rede local (WebSocket na porta
  3000/3001) — liga, desliga, muda de app, conforme o comando recebido.
- **Automação com login persistido** (`fetch-note.mjs` como referência):
  na primeira execução, abre o navegador (Playwright) de forma visível
  para você logar manualmente uma vez; salva o estado da sessão
  (`storageState`) num arquivo; nas execuções seguintes, carrega esse
  estado e já entra autenticado. **Esse arquivo de estado é um segredo —
  nunca committar, nunca sair da VPS sem necessidade.**

Chame essas ferramentas a partir do Hermes (ex: como um "skill"/tool que
o agente pode invocar) ou via `hermes send`/`crontab` para rodarem por
conta própria e reportarem o resultado pelo mesmo canal do Telegram.

## 4. Painel físico (opcional, mas recomendado)

Documentado em detalhe em [panel/SETUP.md](panel/SETUP.md) — cobre desde
copiar os três arquivos (`server.py`, `panel.html`, `manifest.json`) até
configurar o autostart resiliente no Windows (Tarefa Agendada com
`pythonw.exe`, sem console, com restart automático).

## 5. WSL + Kali (controle de rede local)

```powershell
wsl --install -d kali-linux
wsl -d kali-linux -- sudo apt update
wsl -d kali-linux -- sudo apt install -y nmap avahi-utils
```

Isso já habilita a descoberta de rede (`nmap -sn`, resolução mDNS) usada
pelo `panel/server.py`. Para testes de segurança de aplicação (SAST/SCA/
fuzzing/web), qualquer ferramenta equivalente ao "Raptor" descrito em
[ARCHITECTURE.md](ARCHITECTURE.md) serve — Kali já vem com boa parte do
ferramental de segurança pré-instalado.

## Checklist final

- [ ] `curl http://127.0.0.1:20128/v1/models` responde (9Router de pé)
- [ ] `hermes status` mostra `Gateway Service: running` e `Telegram: configured`
- [ ] Uma mensagem de teste no Telegram do bot recebe resposta do agente
- [ ] `hermes secrets` configurado, nenhuma credencial de site em texto puro
- [ ] Painel físico acessível pelo celular na mesma rede (se for usar)
- [ ] `wsl -d kali-linux -- nmap -sn <sua-rede>/24` encontra dispositivos
