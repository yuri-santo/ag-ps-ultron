# Audio do Hermes Desktop: diagnostico e recuperacao

Incidente local de 2026-09-28: `transcribe-audio` retornava
`TimeoutError: The operation was aborted due to timeout`.

## Evidencia e correcao

- Desktop usava o dashboard autenticado em `127.0.0.1:9119`.
- Saude HTTP, STT e TTS chegaram a expirar; microfone e dispositivos de audio
  eram enumerados normalmente no Windows.
- O servico estava com `CPUQuota=50%`, `MemoryHigh=256M`, `MemoryMax=512M`,
  mais de 82 mil eventos `memory.high` e cerca de 622 MB de swap no cgroup.
- Ajuste restrito ao servico: `CPUQuota=200%`, `MemoryHigh=1536M`,
  `MemoryMax=2G`. A saude voltou a HTTP 200 sem reiniciar o servidor.
- TTS respondeu em 7,09 s e STT em 20,261 s no teste direto. O cliente tinha
  prazo de apenas 20 s. O prazo de STT passou para 90 s, sem alterar TTS,
  modelo, voz, personalidade, captura ou mensagens.
- Depois de reiniciar somente o Desktop, a chamada real pelo IPC transcreveu
  corretamente o audio sintetico de teste. A reproducao TTS terminou em
  11,747 s no teste pelo preload. Isso confirma o fluxo testado, nao todos os
  microfones, duracoes, cargas ou redes.

Os limites novos foram persistidos por `systemctl set-property`. Eles sao
tetos, nao reservas. Antes de repetir em outro computador, medir RAM/CPU
disponiveis e o tamanho do modelo. Aumentar somente timeout nao resolve
pressao de memoria ou um servidor sem resposta.

## Reproduzir o diagnostico

Na distribuicao WSL que realmente hospeda o agente:

```bash
systemctl show hermes-dashboard.service -p MemoryCurrent -p MemoryHigh -p MemoryMax -p MemorySwapCurrent -p CPUQuotaPerSecUSec
cat /sys/fs/cgroup/system.slice/hermes-dashboard.service/memory.events
curl --max-time 10 http://127.0.0.1:9119/api/health
```

Primeiro teste reversivel, com memoria disponivel e servico confirmado:

```bash
sudo systemctl set-property --runtime hermes-dashboard.service CPUQuota=200% MemoryHigh=1536M MemoryMax=2G
```

Repetir STT/TTS autenticados sem imprimir tokens nem gravar conversas privadas
nos logs. Se o teste melhorar, aplicar os mesmos valores sem `--runtime`.
Para desfazer neste incidente, os valores anteriores eram 50%, 256M e 512M;
outros ambientes devem guardar seus proprios valores antes de mudar.

No codigo do Desktop, em `src/main/hermes.ts`, funcao `transcribeAudio`,
alterar apenas o `AbortSignal.timeout(20000)` daquela requisicao para `90000`.
Manter autenticacao e erros do servidor. Teste de regressao deve verificar
90.000 ms; nao substituir todos os timeouts do aplicativo.

A instalacao local recebeu migracao pontual do bundle com backup do arquivo
anterior e recalculo da integridade do ASAR, sem incorporar as centenas de
alteracoes preexistentes do checkout. Uma nova compilacao deve usar a mesma
correcao no fonte. O repositorio publico nao inclui binarios nem credenciais.

## Limites

O Desktop permanece com as preferencias de escuta/voz salvas pelo usuario.
Nao ativamos escuta permanente como efeito da correcao. A janela precisa estar
no chat ativo e a escuta habilitada para chamadas pelo nome. Se o problema
retornar, conferir saude e latencia antes de trocar o microfone ou modelo.
