# Ferramentas TOP do GitHub adotadas — 28/09/2026 (parte 3)

Critério: só projetos em destaque (milhares de estrelas, manutenção ativa) ou APIs oficiais.

| Projeto | Estrelas* | Para quem | Como entrou |
|---|---|---|---|
| k2-fsa/sherpa-onnx (+ pyannote-segmentation-3.0, 3D-Speaker) | ~15k | Atas de reunião | Diarização local: "Participante 1..N" na ata e na transcrição |
| NVIDIA Parakeet-TDT 0.6B v3 (via sherpa-onnx) | — | Voz | Testado: WER 6,5% vs 8,1% do Whisper base, mas mesma velocidade e carga de 9 s; mantido o Whisper aquecido na voz do desktop |
| python-docx | ~5k | Atas | Ata formal também em Word editável (e-mail e Telegram) |
| yfinance | ~25k | Buffett, Tron, Bigode | cotacao_b3: preço, 52 semanas, dividendos 12 m |
| BrasilAPI | ~11k | Bigode, Buffett, Tron (e conferência de feriados do Harvey) | brasilapi: feriados, CNPJ, taxas, bancos |
| Banco Central SGS (API oficial) | — | Bigode, Buffett, Tron | bcb_serie: Selic, CDI, IPCA (12 m), IGP-M, PTAX |
| lynis | ~16k | Mr Robot | Auditoria semanal (domingo 04:30) |
| trivy | ~38k | Mr Robot | Vulnerabilidades altas/críticas em stacks, plugins e scripts |
| gitleaks | ~29k | Mr Robot | Segredos esquecidos em arquivos (relatório redigido) |
| restic | ~36k | Todos | Backup diário 03:40, criptografado, em D:\Backups\ultron-restic |
| mcpvault | ~1,7k | Ultron (inglês/Obsidian) | Vault D:\Ingles_NumberOne via MCP, sem abrir o Obsidian |

*Estrelas aproximadas na data da varredura.

## Em destaque, mas dependem de você (login ou decisão)
- **garmin_mcp** (~1,2k★): dados de treino para o Arnold — precisa do seu login Garmin (eu não entro com senha).
- **changedetection.io** (~35k★): alerta de queda de preço — precisa escolher as páginas e o canal de aviso.
- **OCRmyPDF** (~35k★) e **paperless-ngx** (~46k★): arquivo de comprovantes/boletos com OCR — paperless usa 1,5–2 GB de RAM e o WSL está com ~2 GB livres.
- **github-mcp-server** (~33k★): Hércules operar GitHub — precisa de token pessoal com escopo mínimo.
- **promptfoo** (~25k★): testes automáticos dos agentes (Tanos/Ironman).
