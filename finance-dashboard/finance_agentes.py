#!/usr/bin/env python3
"""Discussao com os agentes responsaveis por cada decisao do mapa.

Voce escolhe um caminho e diz por que. Isso abre uma thread com os agentes
daquela area, que recebem o retrato financeiro real e respondem.

O 9Router pode estar fora do ar. Quando estiver, a decisao e o motivo ficam
gravados assim mesmo e a consulta fica pendente - nunca se inventa resposta.
"""
import json
import os
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import datetime

BASE = os.environ.get("NOVE_ROUTER_URL", "")
CHAVE = os.environ.get("NOVE_ROUTER_KEY", "")
MODELO = os.environ.get("MAPA_AGENTE_MODELO", "")
TIMEOUT = 45

# Quem responde por qual tipo de decisao. A chave sai do proprio no da arvore.
AGENTES = {
    "raiz": [
        ("Controlador de Fluxo", "responde por fechar o mes no azul"),
    ],
    "corte": [
        ("Analista de Despesas", "responde por cortar o que menos doi"),
        ("Controlador de Fluxo", "responde pelo impacto no mes"),
    ],
    "horas": [
        ("Negociador de Horas", "responde por destravar e vender hora"),
        ("Controlador de Fluxo", "responde pelo impacto no mes"),
    ],
    "caixa": [
        ("Cobranca e Recebiveis", "responde por puxar o que ja e seu"),
        ("Controlador de Fluxo", "responde pelo impacto no mes"),
    ],
    "meta": [
        ("Planejador de Metas", "responde por proteger o prazo da meta"),
        ("Controlador de Fluxo", "responde pelo impacto no mes"),
    ],
}


def migrar(db_path):
    con = sqlite3.connect(db_path, timeout=10)
    con.executescript(
        "CREATE TABLE IF NOT EXISTS arvore_discussoes("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, criado TEXT, no_id TEXT, rotulo TEXT,"
        " motivo TEXT, agente TEXT, papel TEXT, resposta TEXT, status TEXT,"
        " contexto TEXT);"
        "CREATE INDEX IF NOT EXISTS ix_disc_no ON arvore_discussoes(no_id);"
    )
    con.commit()
    con.close()


def responsaveis(no):
    """Agentes que respondem por um no do mapa."""
    if no.get("tipo") == "raiz":
        return AGENTES["raiz"]
    if no.get("tipo") == "meta":
        return AGENTES["meta"]
    chave = str(no.get("id", ""))
    for marca in ("corte", "horas", "caixa"):
        if marca in chave:
            return AGENTES[marca]
    return AGENTES["meta"]


def abrir(db_path, no, motivo, contexto):
    """Registra a escolha e cria uma pendencia por agente. Devolve os ids."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Escreva o motivo da escolha antes de seguir.")
    if len(motivo) > 2000:
        raise ValueError("Motivo muito longo (limite de 2000 caracteres).")

    agora = datetime.now().isoformat(timespec="seconds")
    ctx = json.dumps(contexto, ensure_ascii=False)
    ids = []
    con = sqlite3.connect(db_path, timeout=10)
    for agente, papel in responsaveis(no):
        cur = con.execute(
            "INSERT INTO arvore_discussoes"
            "(criado,no_id,rotulo,motivo,agente,papel,resposta,status,contexto)"
            " VALUES(?,?,?,?,?,?,NULL,'pendente',?)",
            (agora, no["id"], no["rotulo"], motivo, agente, papel, ctx),
        )
        ids.append(cur.lastrowid)
    con.commit()
    con.close()
    return ids


def thread(db_path, no_id):
    """Historico da discussao daquele no, do mais novo para o mais antigo."""
    con = sqlite3.connect(db_path, timeout=10)
    con.row_factory = sqlite3.Row
    linhas = [dict(r) for r in con.execute(
        "SELECT id,criado,rotulo,motivo,agente,papel,resposta,status "
        "FROM arvore_discussoes WHERE no_id=? ORDER BY id DESC LIMIT 30", (no_id,))]
    con.close()
    return linhas


def pendentes(db_path):
    con = sqlite3.connect(db_path, timeout=10)
    n = con.execute(
        "SELECT COUNT(*) FROM arvore_discussoes WHERE status='pendente'").fetchone()[0]
    con.close()
    return n


# --------------------------------------------------------------------------
# 9Router
# --------------------------------------------------------------------------
_modelo_cache = {"valor": None}


def _http(url, dados=None, timeout=TIMEOUT):
    if not BASE or not CHAVE or os.environ.get("FIN_ENABLE_AI") != "1":
        raise RuntimeError("Consulta externa desabilitada; configure FIN_ENABLE_AI, URL e chave explicitamente")
    req = urllib.request.Request(url, method="GET" if dados is None else "POST")
    req.add_header("Authorization", "Bearer " + CHAVE)
    corpo = None
    if dados is not None:
        corpo = json.dumps(dados).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, corpo, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def escolher_modelo():
    """Pergunta ao proprio router quais modelos existem.

    Fixar um nome quebraria toda vez que o catalogo do gateway mudasse; aqui
    a escolha e feita na hora, com preferencia por modelos de raciocinio.
    """
    if MODELO:
        return MODELO
    if _modelo_cache["valor"]:
        return _modelo_cache["valor"]
    dados = _http(BASE.rstrip("/") + "/models", timeout=15)
    nomes = [m.get("id") for m in dados.get("data", []) if m.get("id")]
    if not nomes:
        raise RuntimeError("o 9Router nao listou nenhum modelo")
    for preferido in ("claude", "gemini-2.5-pro", "gemini", "gpt"):
        for nome in nomes:
            if preferido in nome.lower():
                _modelo_cache["valor"] = nome
                return nome
    _modelo_cache["valor"] = nomes[0]
    return nomes[0]


def _prompt(linha):
    ctx = json.loads(linha["contexto"] or "{}")
    return (
        "Voce e o agente '%s', que %s no planejamento financeiro da pessoa usuaria.\n\n"
        "Ele escolheu seguir este caminho no mapa de decisoes:\n"
        "  CAMINHO: %s\n"
        "  MOTIVO DELE: %s\n\n"
        "Retrato financeiro real, apurado do banco de dados dele agora:\n%s\n\n"
        "Responda em portugues do Brasil, em no maximo 6 linhas, sendo direto:\n"
        "1. Se o caminho faz sentido dado o motivo e os numeros.\n"
        "2. O risco concreto que voce enxerga na sua area.\n"
        "3. Uma acao pratica para as proximas 2 semanas.\n"
        "Nao invente numeros que nao estejam no retrato acima."
        % (linha["agente"], linha["papel"], linha["rotulo"], linha["motivo"],
           json.dumps(ctx, ensure_ascii=False, indent=1))
    )


def _falar(linha):
    resposta = _http(BASE.rstrip("/") + "/chat/completions", {
        "model": escolher_modelo(),
        "messages": [{"role": "user", "content": _prompt(linha)}],
        "max_tokens": 700,
        "temperature": 0.4,
    })
    texto = (resposta.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if not (texto or "").strip():
        raise RuntimeError("o agente respondeu vazio")
    return texto.strip()


def consultar(db_path, ids):
    """Consulta o 9Router para cada pendencia. Sincrono; use `disparar`."""
    if not ids:
        return
    con = sqlite3.connect(db_path, timeout=10)
    con.row_factory = sqlite3.Row
    marcas = ",".join("?" * len(ids))
    linhas = [dict(r) for r in con.execute(
        "SELECT * FROM arvore_discussoes WHERE id IN (%s)" % marcas, list(ids))]
    con.close()

    for linha in linhas:
        try:
            texto, status = _falar(linha), "respondido"
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                ValueError, KeyError, RuntimeError) as exc:
            # Gateway fora ou resposta estranha: a pendencia continua de pe
            # para ser reconsultada depois, com o erro visivel.
            texto, status = "Nao foi possivel falar com o 9Router: %s" % exc, "pendente"
        con = sqlite3.connect(db_path, timeout=10)
        con.execute("UPDATE arvore_discussoes SET resposta=?, status=? WHERE id=?",
                    (texto, status, linha["id"]))
        con.commit()
        con.close()


def disparar(db_path, ids):
    """Consulta em segundo plano para nao travar o clique na tela."""
    if not ids:
        return None
    t = threading.Thread(target=consultar, args=(db_path, list(ids)), daemon=True)
    t.start()
    return t


def reconsultar(db_path, no_id):
    """Tenta de novo tudo que ficou pendente naquele no."""
    con = sqlite3.connect(db_path, timeout=10)
    ids = [r[0] for r in con.execute(
        "SELECT id FROM arvore_discussoes WHERE no_id=? AND status='pendente'", (no_id,))]
    con.close()
    disparar(db_path, ids)
    return len(ids)
