# PhoneHarness: preparacao local

Estado verificado em 2026-09-30: instalado para ajuda, diagnostico e testes
offline. Controle real do Android e integracao operacional com Hermes ainda
nao estao habilitados.

## Instalacao

- Runtime: WSL Debian local, `/opt/phoneharness-1cdc0d9`.
- Fonte: `PhoneHarness/PhoneHarness`, commit
  `1cdc0d963641d517f5deb687adb37332cf844e70`, exportado do clone local existente.
- Python: 3.11.16, venv propria em `.venv`, sem alterar o ambiente do Hermes.
- Dependencia instalada: `PyYAML==6.0.2`. Nenhum pacote foi instalado no Android.
- Launcher: `/opt/phoneharness-1cdc0d9/phoneharness-local`.
- Nenhum servico, porta, proxy, encaminhamento ADB ou modelo foi ativado.

O codigo upstream fica somente no ambiente local. Este diretorio versiona
apenas o launcher, instalador, testes e documentacao originais; nao redistribui
o upstream, cuja licenca precisa ser esclarecida antes de redistribuicao.
O instalador exporta o commit fixo, exclui `.env`/`.env.*` e recusa sobrescrever
uma instalacao existente. Uma instalacao interrompida exige inspecao manual
antes de qualquer tentativa de substituicao.

```powershell
wsl -d Debian -u root -- /opt/phoneharness-1cdc0d9/phoneharness-local --help
wsl -d Debian -u root -- /opt/phoneharness-1cdc0d9/phoneharness-local diagnose
wsl -d Debian -u root -- /opt/phoneharness-1cdc0d9/phoneharness-local upstream-help
wsl -d Debian -u root -- /opt/phoneharness-1cdc0d9/phoneharness-local self-test
```

`diagnose` apenas consulta arquivos locais: nao descobre aparelhos, nao chama
ADB e nao acessa a rede. `upstream-help` e `self-test` removem o ambiente herdado
e executam em namespace de rede vazio com `unshare --net`; falham se esse
isolamento nao puder ser criado. Isso isola a rede, nao o sistema de arquivos.
O launcher nao e uma sandbox para executar codigo arbitrario nao confiavel.

O launcher rejeita console, servidores, probes, comandos livres e operacoes
no aparelho. Argumentos extras tambem sao rejeitados. Chamar o upstream
diretamente contorna essa protecao e nao faz parte desta preparacao.

## Evidencia

- Ajuda upstream: exit 0 dentro do namespace sem rede.
- Testes upstream: 11/11 passaram, sem rede e sem aparelho.
- Testes do launcher: 6/6 passaram; rejeicao antes de subprocessos, diagnostico
  sem execucao externa, argumentos extras recusados, ambiente sem credenciais
  herdadas e falha obrigatoria na ausencia de `unshare`.
- Diagnostico: venv/source presentes; `operations_enabled: false`.

Esses testes nao validam pareamento, captura de tela, toques, aplicacoes,
modelos ou funcionamento ponta a ponta.

## Limites confirmados no codigo

1. `scripts/gui_proxy.py` escuta em `0.0.0.0` sem autenticacao. Nao iniciar
   esse proxy na LAN ou WireGuard sem primeiro corrigir seu acesso.
2. `phoneharness/cli.py` possui enderecos e modelos padrao. O console pode
   selecionar execucao local quando nao ha serial; um operador futuro deve
   exigir aparelho, modelo e endpoints explicitos e validacao do destino.
3. O backend ADB referencia helpers ausentes da distribuicao publica,
   incluindo `scripts/health_check.sh` e `scripts/adb_ubuntu_exec.sh`.
   Instalar o pacote nao basta para habilitar essas rotinas device-side.
4. A camada GUI importa Pillow em caminhos executados apenas durante uso.
   Pillow nao foi instalado nesta preparacao minima.
5. O ambiente de referencia presume emulador/Termux e ferramentas no aparelho.
   Compatibilidade com um Android fisico ainda precisa ser validada.

## Proxima etapa no Android

O aparelho fisico foi identificado e autorizado pelo ADB Windows via USB.
A versao observada e Android 10. Nao confundir com o pareamento TLS por codigo
das versoes mais novas: nao foi aberto ADB TCP legado na LAN/WireGuard.
Serial e enderecos ficam somente na documentacao privada da maquina.
O Deck deste repositorio e uma PWA em `panel/`, nao um aplicativo nativo
necessariamente identificavel pelo nome do pacote Android.

A existencia de WireGuard nao comprova que o servico ADB esteja acessivel
nesse endereco. Nao houve varredura de rede nem tentativa de pareamento.
Primeiro deve-se validar o endpoint escolhido e a autorizacao do aparelho;
depois, uma leitura limitada que identifique o serial esperado. Nenhuma
instalacao, permissao de acessibilidade, aplicativo, teclado ou configuracao
do telefone foi alterada por esta preparacao.

O ADB observado esta no Windows; o runtime acima esta no WSL. A escolha de
ponte Windows/WSL ou cliente ADB Linux deve ser explicita na proxima etapa,
sem iniciar um servidor ADB publicamente acessivel. Modelos e credenciais
tambem continuam pendentes, sem fallback implicito.

Nao ha servico externo, VPS, cron, plugin Hermes ou operador autonomo novo.
