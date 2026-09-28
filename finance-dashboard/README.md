# Dashboard financeiro

Adaptacao publica do dashboard local do Ultron, em Dash/Flask e SQLite.
Inclui visao geral, despesas, contas, cartoes, assinaturas, horas,
recebimentos, carteira, metas, reservas, mapa de decisoes e cenarios.

Nao e copia byte a byte da instalacao privada. A interface principal foi
adaptada para usar somente dados da base; regras pessoais, clientes, saude,
senhas, bases, imagens privadas e exportadores particulares foram excluidos.
Os modulos de calculo e visualizacao mantêm a estrutura da instalacao de origem.

## Executar no Windows

Python 3.11 ou superior, com pacotes compativeis com a plataforma:

```powershell
cd finance-dashboard
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python bootstrap.py --demo
$env:DASHBOARD_PASSWORD = Read-Host 'Defina a senha local'
.venv\Scripts\python app.py
```

Abra `http://127.0.0.1:9501`. A senha nao e publicada nem tem valor padrao.
`bootstrap.py` recusa substituir banco existente. Sem `--demo`, cria uma
base vazia. Dados de demonstracao sao inteiramente ficticios, nao recomendacoes.

No Linux, use `.venv/bin/python` e defina a variavel de senha no ambiente.
Variaveis opcionais: `FIN_DATA_DIR`, `FIN_DB_PATH`, `FIN_PORT`. A chave de
sessao e criada em `FIN_DATA_DIR`; nao a publique. Nao exponha este servidor
diretamente na internet. TLS, proxy e politica de acesso exigem configuracao
propria. Nenhuma movimentacao bancaria ou ordem de investimento e executada.

Consultas opcionais ao modelo no mapa usam `NOVE_ROUTER_URL`,
`NOVE_ROUTER_KEY` e `MAPA_AGENTE_MODELO`, sem credenciais padrao. Sem provedor,
a consulta fica pendente, nao recebe uma resposta simulada. Configure somente
um endpoint autorizado a receber os dados financeiros que voce cadastrar.
O mapa geografico opcional consulta OpenStreetMap com as coordenadas informadas.

## Verificar

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

Os testes usam banco temporario sintetico. O dashboard pede confirmacao pelo
botao Salvar para gravar edicoes e detecta edicao concorrente. A instalacao
financeira privada do usuario nao e migrada ou substituida por este exemplo.
