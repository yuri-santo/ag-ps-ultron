# Transcricao local

`parakeet_cli.py` e `diarizar.py` atendem os fluxos existentes. A segunda
passagem `reprocess.py` usa faster-whisper sem alterar eventos ou banco.

## Segunda passagem revisavel

Instale `numpy`, `soundfile` e `faster-whisper` em ambiente Python compativel.
As faixas estao em `agent/requirements-reprocess.txt`.
O modelo precisa estar no cache local; download exige `--allow-download`.

```powershell
python agent/stt/reprocess.py --audio-dir CAMINHO/audio --events CAMINHO/events.jsonl --output-dir CAMINHO/revisao --model small --selection low-confidence --limit 3 --threads 4
python -m unittest discover -s agent/stt -p "test_reprocess.py" -v
```

Entradas: FLAC 16 kHz com nome `<epoch>_<mic|loopback>_<id>.flac` e eventos
JSONL de captura com `id`, `audio_file`, `kind=transcript` e `confidence`.
Contexto de ate dois segundos por lado, apenas no mesmo canal e em arquivos
contiguos. Palavras sao limitadas ao trecho central por seus tempos.

Saidas: `candidates.jsonl`, `manifest.json`, `checkpoints/`. Eventos candidatos
tem tipo distinto e exigem revisao. O manifesto pode estar `partial`,
`complete` ou `failed`; `complete` significa processamento, nao aprovacao
da transcricao. Repetir o comando retoma checkpoints compativeis. `--limit`
limita trabalho novo por execucao.

Use diretorio de saida exclusivo. Preserve audios e eventos originais.
Nenhum texto e automaticamente promovido a decisao, compromisso, relatorio
final ou identidade de falante. Audio pessoal e saidas ficam fora do Git.
