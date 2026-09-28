#!/usr/bin/env python3
"""Mapa de decisoes: o agente traca, voce escolhe o caminho.

A arvore nao e escrita a mao. Ela nasce do estado do banco (finance_engine) e
e redesenhada sozinha toda vez que o fingerprint financeiro muda - entrada,
saida, hora lancada, ticket sincronizado, meta atualizada.

Voce nao edita premissas aqui. Clicar num ramo abre o que aquele caminho exige,
o fluxo mes a mes e a visao por ano. Seguir o caminho e um ato deliberado: voce
escreve o motivo, e isso abre a discussao com os agentes responsaveis.
"""
import json
import uuid
import re
from datetime import datetime

import finance_agentes as agentes
from finance_canvas import annual_board, viewport
from finance_engine import (alavancas, brl, conectar, estado, fluxo_ano,
                            fluxo_mensal, mes_que_fecha, visao_anual)

# Geometria do mapa. As coordenadas saem daqui em px e sao compartilhadas
# pelos nos (divs) e pelas ligacoes, por isso nada de escala.
# A arvore cresce da esquerda para a direita: nivel vira coluna, ramo vira
# linha. Na vertical a largura explodia (3282px) e os cotovelos atravessavam a
# tela inteira, um por cima do outro. Assim a largura fica fixa em ~1480px e o
# crescimento vai para a altura, que rola naturalmente.
NO_W, NO_H = 252, 132
CAMADA_X, LINHA_Y = 344, 158
MARGEM = 48
HORIZONTE = 24  # meses projetados no pop-up

LARGURA_MAX = {1: 3, 2: 2, 3: 2}  # ramos por no, de nivel em nivel


# --------------------------------------------------------------------------
# persistencia
# --------------------------------------------------------------------------
def migrar(db_path):
    with conectar(db_path) as con:
        con.executescript(
            "CREATE TABLE IF NOT EXISTS arvore_snapshots("
            " id TEXT PRIMARY KEY, criado TEXT, mes TEXT, fingerprint TEXT, nos TEXT);"
            "CREATE TABLE IF NOT EXISTS arvore_caminho("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, criado TEXT, no_id TEXT,"
            " rotulo TEXT, fingerprint TEXT);"
            "CREATE TABLE IF NOT EXISTS arvore_eventos("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, criado TEXT, tipo TEXT, texto TEXT);"
        )
    agentes.migrar(db_path)


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def registrar_evento(con, tipo, texto):
    con.execute(
        "INSERT INTO arvore_eventos(criado, tipo, texto) VALUES(?,?,?)", (_agora(), tipo, texto)
    )


def sincronizar(db_path, est, nos):
    """Grava snapshot quando o estado financeiro muda. Devolve (mudou, eventos, trilha)."""
    with conectar(db_path) as con:
        ultimo = con.execute(
            "SELECT fingerprint, nos FROM arvore_snapshots WHERE mes=? "
            "ORDER BY criado DESC, rowid DESC LIMIT 1", (est["mes"],)
        ).fetchone()
        mudou = ultimo is None or ultimo["fingerprint"] != est["fingerprint"]
        if mudou:
            antes = len(json.loads(ultimo["nos"])) if ultimo else 0
            con.execute(
                "INSERT INTO arvore_snapshots(id, criado, mes, fingerprint, nos) VALUES(?,?,?,?,?)",
                (uuid.uuid4().hex, _agora(), est["mes"], est["fingerprint"], json.dumps(nos)),
            )
            if ultimo is None:
                registrar_evento(
                    con, "inicio", "Mapa tracado pela primeira vez: %d decisoes abertas." % len(nos)
                )
            else:
                registrar_evento(
                    con, "readapta",
                    "Movimentacao detectada. Mapa refeito: %d decisoes abertas (%+d)."
                    % (len(nos), len(nos) - antes),
                )
        eventos = [dict(r) for r in con.execute(
            "SELECT criado, tipo, texto FROM arvore_eventos ORDER BY id DESC LIMIT 8")]
        trilha = [dict(r) for r in con.execute(
            "SELECT c.no_id, c.rotulo, c.criado FROM arvore_caminho c "
            "WHERE c.no_id LIKE ? OR (instr(c.no_id,'::')=0 AND EXISTS ("
            "SELECT 1 FROM arvore_snapshots s WHERE s.fingerprint=c.fingerprint AND s.mes=?)) "
            "ORDER BY c.id", (est["mes"] + "::%", est["mes"]))]
        for passo in trilha:
            if "::" not in passo["no_id"]:
                passo["no_id"] = est["mes"] + "::" + passo["no_id"]
    return mudou, eventos, trilha


def andar(db_path, no_id, rotulo, fingerprint):
    """Marca um ramo como percorrido. Repetir o mesmo no desfaz o passo."""
    with conectar(db_path) as con:
        atual = con.execute(
            "SELECT id, no_id FROM arvore_caminho WHERE no_id LIKE ? ORDER BY id DESC LIMIT 1",
            (no_id.split("::", 1)[0] + "::%" if "::" in no_id else "%",)
        ).fetchone()
        if atual and atual["no_id"] == no_id:
            con.execute("DELETE FROM arvore_caminho WHERE id=?", (atual["id"],))
            registrar_evento(con, "volta", "Passo desfeito: %s" % rotulo)
            return False
        con.execute(
            "INSERT INTO arvore_caminho(criado, no_id, rotulo, fingerprint) VALUES(?,?,?,?)",
            (_agora(), no_id, rotulo, fingerprint),
        )
        registrar_evento(con, "passo", "Caminho escolhido: %s" % rotulo)
        return True


def gerar_mensal(est):
    """Keep amounts untouched while giving every decision a stable month identity."""
    prefix = est["mes"] + "::"
    nodes = gerar(est)
    for node in nodes:
        node["id"] = prefix + node["id"]
        node["pai"] = prefix + node["pai"] if node["pai"] else None
    nodes[0]["rotulo"] = "Mês de " + est["mes"]
    return nodes


def mes_do_no(no_id):
    if not isinstance(no_id, str):
        return None
    match = re.fullmatch(r"(\d{4}-(?:0[1-9]|1[0-2]))::.+", no_id)
    return match.group(1) if match else None


def fluxo_calendario(db_path, ano):
    """A calendar year always uses the current engine anchor, not the selected month."""
    return fluxo_ano(db_path, estado(db_path), str(ano))


# --------------------------------------------------------------------------
# o agente: monta a arvore a partir do estado
# --------------------------------------------------------------------------
def ajuste_de(usadas, meta_falta=0.0):
    """Traduz alavancas escolhidas no ajuste que o fluxo mensal entende.

    Assinatura entra como CORTE (o fluxo apaga a saida) e nao como ganho, e
    fim de parcela nao entra de jeito nenhum - o fluxo ja derruba a parcela no
    mes certo. Somar os dois contaria o mesmo dinheiro duas vezes.
    """
    mensal = sum(a["mensal"] for a in usadas if a["id"].startswith("horas:"))
    pontual = sum(a["pontual"] for a in usadas)
    cortes = [int(a["id"].split(":", 1)[1]) for a in usadas if a["id"].startswith("corte:")]
    return {"mensal": round(mensal, 2), "pontual": round(pontual, 2),
            "cortes": cortes, "meta_falta": round(meta_falta, 2)}


def _req(texto, valor, fonte):
    return {"texto": texto, "valor": valor, "fonte": fonte}


def _requisitos_raiz(est):
    """Abre a despesa exatamente como o resto do dashboard a calcula."""
    req = [
        _req("Renda do mes", "R$ " + brl(est["renda_mes"]), est["fontes"]["renda_mes"]),
        _req("Contas que nao sao de cartao", "R$ " + brl(est["fixas"]), est["fontes"]["fixas"]),
    ]
    for nome, f in sorted(est["faturas"].items()):
        req.append(_req(
            "Fatura %s" % nome, "R$ " + brl(f["total"]),
            "parcelas R$ %s + assinaturas R$ %s - credito R$ %s"
            % (brl(f["parcelas"]), brl(f["assinaturas"]), brl(f["credito"]))))
    req.append(_req("Parcelas cobradas neste mes (%d)" % len(est["parcelas"]),
                    "R$ " + brl(est["total_parcelas"]), est["fontes"]["parcelas"]))
    return req


def _rotas_resgate(est, alavs):
    """Sobra negativa: antes de qualquer meta, o mes precisa fechar no azul."""
    deficit = abs(est["sobra"])
    cortes = [a for a in alavs
              if a["tipo"] == "recorrente" and a["id"].startswith(("corte:", "parcela:"))]
    horas = [a for a in alavs if a["id"].startswith("horas:")]
    caixa = [a for a in alavs if a["tipo"] == "pontual"]
    rotas = []

    if cortes:
        soma, usados = 0.0, []
        for a in sorted(cortes, key=lambda x: -x["mensal"]):
            if soma >= deficit:
                break
            soma += a["mensal"]
            usados.append(a)
        rotas.append({
            "chave": "corte", "rotulo": "Enxugar o fixo",
            "sub": " + ".join(a["rotulo"] for a in usados),
            "ganho_mensal": soma, "ganho_pontual": 0.0,
            "risco": "baixo", "alavancas": usados,
        })

    if horas:
        melhor = max(horas, key=lambda x: x["mensal"])
        rotas.append({
            "chave": "horas", "rotulo": "Vender mais horas",
            "sub": melhor["detalhe"], "ganho_mensal": melhor["mensal"], "ganho_pontual": 0.0,
            "risco": melhor["risco"], "alavancas": [melhor],
        })

    # Fila travada (risco alto) nao entra como caixa certo: vira acelerador.
    caixa_certa = [a for a in caixa if a["risco"] != "alto"]
    if caixa_certa:
        rotas.append({
            "chave": "caixa", "rotulo": "Puxar o que ja e seu",
            "sub": " + ".join(a["rotulo"] for a in caixa_certa[:3]),
            "ganho_mensal": 0.0, "ganho_pontual": sum(a["pontual"] for a in caixa_certa),
            "risco": "medio", "alavancas": caixa_certa,
        })

    if cortes and horas:
        corte_top = max(cortes, key=lambda x: x["mensal"])
        hora_top = min(horas, key=lambda x: x["mensal"])
        rotas.append({
            "chave": "mista", "rotulo": "Combinar corte e hora",
            "sub": "%s + %s" % (corte_top["rotulo"], hora_top["rotulo"]),
            "ganho_mensal": corte_top["mensal"] + hora_top["mensal"], "ganho_pontual": 0.0,
            "risco": "medio", "alavancas": [corte_top, hora_top],
        })

    return rotas[: LARGURA_MAX[1]]


def _rotas_avanco(est, alavs):
    """Sobra positiva: as rotas passam a ser formas de acelerar."""
    rotas = [{
        "chave": "manter", "rotulo": "Manter o ritmo",
        "sub": "Sobra de R$ %s por mes, sem mexer em nada" % brl(est["sobra"]),
        "ganho_mensal": 0.0, "ganho_pontual": 0.0, "risco": "baixo", "alavancas": [],
    }]
    recorrentes = [a for a in alavs if a["tipo"] == "recorrente" and a["id"] != "sobra"]
    pontuais = [a for a in alavs if a["tipo"] == "pontual" and a["risco"] != "alto"]

    for a in sorted(recorrentes, key=lambda x: -x["mensal"])[:2]:
        rotas.append({
            "chave": "acel:%s" % a["id"], "rotulo": a["rotulo"], "sub": a["detalhe"],
            "ganho_mensal": a["mensal"], "ganho_pontual": 0.0,
            "risco": a["risco"], "alavancas": [a],
        })
    if pontuais:
        rotas.append({
            "chave": "caixa", "rotulo": "Puxar o que ja e seu",
            "sub": " + ".join(a["rotulo"] for a in pontuais[:3]),
            "ganho_mensal": 0.0, "ganho_pontual": sum(a["pontual"] for a in pontuais),
            "risco": "medio", "alavancas": pontuais,
        })
    return rotas[: LARGURA_MAX[1]]


def _capacidade(sobra, pontual):
    """Enquanto o fluxo do mes for negativo, nada sobra para meta.

    Dinheiro pontual que entra com o mes no vermelho vai tapar o rombo, nao
    engordar meta - por isso ele so conta quando a sobra ja virou.
    """
    if sobra < 0:
        folego = int(pontual // abs(sobra)) if pontual > 0 else 0
        return 0.0, 0.0, folego
    return sobra, pontual, None


def _classe_mes(linha):
    """Mes sem lancamento nao e nem realizado nem previsao: e buraco no banco."""
    if linha.get("sem_dados"):
        return "vazio"
    return "realizado" if linha["realizado"] else "previsto"


def _progresso(linha, fecha):
    """Texto do acumulado. Repetir '100% da meta' em todo mes nao informa nada."""
    if linha["pct"] is None:
        return "sem meta neste ramo"
    if fecha and linha["i"] > fecha["i"]:
        return "meta fechada em %s" % fecha["mes"]
    if fecha and linha["i"] == fecha["i"]:
        return "meta fechada aqui"
    return "%.0f%% da meta" % linha["pct"]


def _meses_txt(m):
    if m == 0:
        return "no proprio mes"
    return "1 mes" if m == 1 else "%d meses" % m


def _status(meses, prazo):
    if meses is None:
        return "critico"
    if prazo is None:
        return "ok"
    return "ok" if meses <= prazo else ("risco" if meses <= prazo + 6 else "critico")


def prazo_projetado(est, ajuste):
    """Meses ate a meta fechar, pelo fluxo real - nao pela sobra de hoje.

    A conta estatica ignora que as parcelas acabam, e por isso dizia "nao
    fecha" para meta que o fluxo fecha em poucos meses. O card e o pop-up
    precisam contar a mesma historia, entao os dois saem daqui.
    """
    if not ajuste.get("meta_falta"):
        return None, None
    fluxo = fluxo_mensal(est["db"], est, ajuste, HORIZONTE)
    fecha = mes_que_fecha(fluxo)
    return (fecha["i"], fecha["mes"]) if fecha else (None, None)


def gerar(est):
    """Devolve a lista de nos ja posicionada. Sem estado externo, so o banco."""
    alavs = alavancas(est)
    resgate = est["sobra"] <= 0

    nos = [{
        "id": "raiz", "nivel": 0, "pai": None, "tipo": "raiz",
        "rotulo": "Hoje - %s" % est["mes"],
        "sub": "Modo resgate: o mes fecha no vermelho" if resgate
               else "Modo avanco: sobra livre no mes",
        "valor": ("Deficit de R$ %s" % brl(abs(est["sobra"]))) if resgate
                 else ("Sobra de R$ %s" % brl(est["sobra"])),
        "meses": None, "status": "critico" if resgate else "ok",
        "nota": "R$ %s de renda contra R$ %s de despesa"
                % (brl(est["renda_mes"]), brl(est["despesas_total"])),
        "ajuste": ajuste_de([]), "requisitos": _requisitos_raiz(est), "meta_id": None,
    }]

    rotas = _rotas_resgate(est, alavs) if resgate else _rotas_avanco(est, alavs)
    metas = [m for m in est["metas"] if m["falta"] > 0][: LARGURA_MAX[2]]

    for rota in rotas:
        nova_sobra = est["sobra"] + rota["ganho_mensal"]
        rid = "rota:%s" % rota["chave"]
        if rota["ganho_mensal"]:
            valor = "Sobra vai a R$ %s/mes" % brl(nova_sobra)
        elif rota["ganho_pontual"]:
            valor = "Entrada unica de R$ %s" % brl(rota["ganho_pontual"])
        else:
            valor = "Sobra segue em R$ %s/mes" % brl(nova_sobra)
        req_rota = [_req(a["rotulo"], a["detalhe"], a["fonte"]) for a in rota["alavancas"]] or \
                   [_req("Seguir sem mexer em nada", rota["sub"], "estado atual do banco")]
        nos.append({
            "id": rid, "nivel": 1, "pai": "raiz", "tipo": "rota",
            "rotulo": rota["rotulo"], "sub": rota["sub"], "valor": valor,
            "meses": None, "status": "ok" if nova_sobra >= 0 else "risco",
            "nota": "risco %s" % rota["risco"],
            "ajuste": ajuste_de(rota["alavancas"]), "requisitos": req_rota, "meta_id": None,
        })

        # Capacidade que a rota entrega as metas, ja descontando o rombo.
        cap, pontual_rota, folego = _capacidade(nova_sobra, rota["ganho_pontual"])

        for meta in metas:
            aj_meta = ajuste_de(rota["alavancas"], meta["falta"])
            meses, mes_fecha = prazo_projetado(est, aj_meta)
            mid = "%s|meta:%s" % (rid, meta["id"])
            if meses is not None:
                valor_meta = "Fecha em %s - %s" % (_meses_txt(meses), mes_fecha)
            elif folego:
                valor_meta = ("Nao fecha em %dm: da %s de folego"
                              % (HORIZONTE, _meses_txt(folego)))
            else:
                valor_meta = "Nao fecha dentro de %d meses" % HORIZONTE
            nos.append({
                "id": mid, "nivel": 2, "pai": rid, "tipo": "meta",
                "rotulo": meta["nome"],
                "sub": "Falta R$ %s de R$ %s" % (brl(meta["falta"]), brl(meta["alvo"])),
                "valor": valor_meta,
                "meses": meses, "status": _status(meses, meta["prazo_meses"]),
                "nota": "prazo da meta: %s" % (meta["data_alvo"] or "sem data"),
                "ajuste": aj_meta,
                "meta_id": meta["id"],
                "requisitos": req_rota + [
                    _req("Juntar o que falta da meta", "R$ " + brl(meta["falta"]),
                         est["fontes"]["metas"]),
                    _req("Prazo combinado", meta["data_alvo"] or "sem data",
                         est["fontes"]["metas"]),
                ],
            })

            # Nivel 3: o que ainda acelera a meta, sem repetir o que a rota usou.
            ja_usadas = {a["id"] for a in rota["alavancas"]}
            extras = [a for a in alavs if a["id"] not in ja_usadas and a["id"] != "sobra"]
            extras.sort(key=lambda a: -(a["mensal"] + a["pontual"] / 12.0))
            for extra in extras[: LARGURA_MAX[3]]:
                aj_extra = ajuste_de(rota["alavancas"] + [extra], meta["falta"])
                meses2, mes_fecha2 = prazo_projetado(est, aj_extra)
                _, _, folego2 = _capacidade(
                    nova_sobra + extra["mensal"], rota["ganho_pontual"] + extra["pontual"]
                )
                ganho = None if (meses is None or meses2 is None) else meses - meses2
                if meses2 is not None:
                    valor_extra = "Fecha em %s - %s" % (_meses_txt(meses2), mes_fecha2)
                elif folego2:
                    valor_extra = "Ainda nao fecha: %s de folego" % _meses_txt(folego2)
                else:
                    valor_extra = "Ainda nao fecha em %d meses" % HORIZONTE
                nos.append({
                    "id": "%s|extra:%s" % (mid, extra["id"]), "nivel": 3, "pai": mid,
                    "tipo": "extra", "rotulo": extra["rotulo"], "sub": extra["detalhe"],
                    "valor": valor_extra,
                    "meses": meses2, "status": _status(meses2, meta["prazo_meses"]),
                    "nota": ("adianta %s" % _meses_txt(ganho)) if ganho
                            else "risco %s" % extra["risco"],
                    "ajuste": aj_extra,
                    "meta_id": meta["id"],
                    "requisitos": req_rota + [
                        _req(extra["rotulo"], extra["detalhe"], extra["fonte"]),
                        _req("Juntar o que falta da meta", "R$ " + brl(meta["falta"]),
                             est["fontes"]["metas"]),
                    ],
                })

    return _posicionar(nos)


def _posicionar(nos):
    """Layout de arvore: folhas ocupam colunas, pais centralizam sobre os filhos."""
    por_id = {n["id"]: n for n in nos}
    filhos = {}
    for n in nos:
        filhos.setdefault(n["pai"], []).append(n["id"])

    coluna = [0]

    def caminhar(nid):
        meus = filhos.get(nid, [])
        if not meus:
            x = float(coluna[0])
            coluna[0] += 1
            por_id[nid]["col"] = x
            return x
        centros = [caminhar(f) for f in meus]
        por_id[nid]["col"] = sum(centros) / len(centros)
        return por_id[nid]["col"]

    caminhar("raiz")
    for n in nos:
        n["x"] = MARGEM + n["nivel"] * CAMADA_X
        n["y"] = MARGEM + n["col"] * LINHA_Y
        # Profundidade: quanto mais fundo o ramo, mais longe ele parece.
        n["z"] = round(1.0 - n["nivel"] * 0.09, 3)
    return nos


def dimensoes(nos):
    largura = max(n["x"] for n in nos) + NO_W + MARGEM
    altura = max(n["y"] for n in nos) + NO_H + MARGEM
    return int(largura), int(altura)


def conectores(nos, ativos):
    """Ligacoes pai -> filho como caixas CSS, nao SVG.

    O Dash sanitiza `<svg>` dentro de Markdown e sobra path orfao, que nao
    desenha nada. Aqui cada aresta vira dois divs: um tronco que sai do pai na
    horizontal e um cotovelo arredondado que desce (ou sobe) ate a linha do
    filho. Como cada nivel tem coluna propria, dois cotovelos nunca se cruzam.
    """
    por_id = {n["id"]: n for n in nos}
    arestas = []
    for n in nos:
        if not n["pai"]:
            continue
        p = por_id[n["pai"]]
        xp, xf = p["x"] + NO_W, n["x"]
        yp, yf = p["y"] + NO_H / 2.0, n["y"] + NO_H / 2.0
        meio = xp + (xf - xp) * 0.45
        classe = "trilha" if n["id"] in ativos else "ramo"

        arestas.append({
            "classe": "lig trilho " + classe,
            "left": xp, "top": yp - 1, "width": max(1.0, meio - xp), "height": 2,
            "lado": None,
        })
        if abs(yf - yp) < 1:
            arestas.append({
                "classe": "lig trilho " + classe,
                "left": meio, "top": yp - 1, "width": max(1.0, xf - meio), "height": 2,
                "lado": None,
            })
        else:
            # Desce pelo lado esquerdo e sai pela base (filho abaixo) ou pelo
            # topo (filho acima); o border-radius nesse canto vira a curva.
            desce = yf > yp
            arestas.append({
                "classe": "lig cotovelo " + classe,
                "left": meio, "top": min(yp, yf) - 1,
                "width": max(1.0, xf - meio), "height": abs(yf - yp) + 2,
                "lado": "baixo" if desce else "cima",
            })
    return arestas


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
def install(app, db_path, is_authed):
    from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
    import dash_bootstrap_components as dbc

    migrar(db_path)

    def kpi(rotulo, valor, fonte, tom="neutro"):
        return html.Div([
            html.Div(rotulo, className="kpi-rotulo"),
            html.Div(valor, className="kpi-valor"),
            html.Div(fonte, className="kpi-fonte"),
        ], className="neu-kpi tom-%s" % tom)

    def cartao_no(n, estado_no):
        return html.Div(
            [
                html.Div(n["rotulo"], className="no-titulo"),
                html.Div(n["sub"], className="no-sub"),
                html.Div(n["valor"], className="no-valor"),
                html.Div(n.get("nota", ""), className="no-nota"),
            ],
            id={"type": "mapa-no", "id": n["id"]},
            n_clicks=0, tabIndex=0, role="button",
            className="neu-no nivel-%d st-%s estado-%s" % (n["nivel"], n["status"], estado_no),
            style={
                "left": "%dpx" % n["x"], "top": "%dpx" % n["y"],
                "width": "%dpx" % NO_W, "minHeight": "%dpx" % NO_H,
                "--z": n["z"],
            },
            title="%s - %s" % (n["sub"], n["valor"]),
        )

    # ---------------- conteudo do pop-up ----------------
    def bloco_requisitos(no):
        return html.Div([
            html.H6("O que este caminho exige", className="pop-h"),
            html.Div([
                html.Div([
                    html.Div(r["texto"], className="req-texto"),
                    html.Div(r["valor"], className="req-valor"),
                    html.Div(r["fonte"], className="req-fonte"),
                ], className="neu-req") for r in no.get("requisitos", [])
            ], className="req-grade"),
        ])

    def barra(valor, teto, classe):
        larg = 0 if teto <= 0 else max(1.5, min(100.0, abs(valor) / teto * 100.0))
        return html.Div(html.Div(className="barra-fill " + classe,
                                 style={"width": "%.1f%%" % larg}), className="barra")

    def bloco_fluxo(no, est):
        fluxo = fluxo_mensal(db_path, est, no["ajuste"], HORIZONTE)
        teto = max([l["entrada"] for l in fluxo] + [l["saida"] for l in fluxo] + [1.0])
        fecha = mes_que_fecha(fluxo)
        falta = no["ajuste"].get("meta_falta") or 0.0

        if falta > 0:
            resumo = ("Fecha a meta em %s, acumulando R$ %s."
                      % (fecha["mes"], brl(fecha["acumulado"]))) if fecha else \
                     ("Nao fecha a meta dentro de %d meses." % HORIZONTE)
        else:
            primeira = next((l for l in fluxo if l["sobra"] > 0), None)
            resumo = ("O mes vira para o azul em %s." % primeira["mes"]) if primeira else \
                     ("O mes segue negativo pelos proximos %d meses." % HORIZONTE)

        linhas = [
            html.Div([
                html.Div(l["mes"], className="fx-mes"),
                html.Div([
                    html.Div([html.Span("entra"), html.Span("R$ " + brl(l["entrada"]))],
                             className="fx-par"),
                    barra(l["entrada"], teto, "boa"),
                    html.Div([html.Span("sai"), html.Span("R$ " + brl(l["saida"]))],
                             className="fx-par"),
                    barra(l["saida"], teto, "ruim"),
                ], className="fx-barras"),
                html.Div([
                    html.Div("R$ " + brl(l["sobra"]),
                             className="fx-sobra " + ("pos" if l["sobra"] >= 0 else "neg")),
                    html.Div("parcelas R$ " + brl(l["parcelas"]), className="fx-detalhe"),
                ], className="fx-num"),
                html.Div([
                    html.Div("R$ " + brl(l["acumulado"]), className="fx-acum"),
                    html.Div(_progresso(l, fecha), className="fx-detalhe"),
                ], className="fx-num"),
            ], className="fx-linha" + (" fecha" if fecha and l["i"] == fecha["i"] else ""))
            for l in fluxo
        ]

        return html.Div([
            html.Div(resumo, className="pop-resumo"),
            html.Div([
                html.Div("mes", className="fx-mes"),
                html.Div("entra / sai", className="fx-barras"),
                html.Div("sobra", className="fx-num"),
                html.Div("acumulado", className="fx-num"),
            ], className="fx-linha fx-cab"),
            html.Div(linhas, className="fx-corpo"),
            html.Div("Projecao com as contas reais por vencimento; cada parcela pesa "
                     "so pelos meses que ainda lhe restam. Gasto variavel usa a media "
                     "dos meses ja fechados.", className="pop-nota"),
        ])

    def bloco_ano(no, est):
        """Os 12 meses do ano lado a lado: realizado a esquerda, previsto a direita."""
        linhas = fluxo_ano(db_path, est, est["mes"][:4], no["ajuste"])
        teto = max([abs(l["entrada"]) for l in linhas] +
                   [abs(l["saida"]) for l in linhas] + [1.0])
        fechados = [l for l in linhas if l["fechado"]]
        futuros = [l for l in linhas if not l["realizado"]]

        colunas = [
            html.Div([
                html.Div(l["rotulo"], className="col-mes"),
                html.Div([
                    html.Div(className="col-barra entra",
                             style={"height": "%.1f%%" % (l["entrada"] / teto * 100.0)},
                             title="entra R$ " + brl(l["entrada"])),
                    html.Div(className="col-barra sai",
                             style={"height": "%.1f%%" % (l["saida"] / teto * 100.0)},
                             title="sai R$ " + brl(l["saida"])),
                ], className="col-par"),
                html.Div("R$ " + brl(l["sobra"], 0),
                         className="col-sobra " + ("pos" if l["sobra"] >= 0 else "neg")),
            ], className="col-ano " + ("realizado" if l["realizado"] else "previsto"),
                title="%s · entra R$ %s · sai R$ %s · sobra R$ %s"
                      % (l["mes"], brl(l["entrada"]), brl(l["saida"]), brl(l["sobra"])))
            for l in linhas
        ]

        resumo = ("%d meses ja fechados, %d ainda por vir. Realizado soma R$ %s de sobra; "
                  "a previsao acrescenta R$ %s."
                  % (len(fechados), len(futuros),
                     brl(sum(max(0.0, l["sobra"]) for l in fechados)),
                     brl(sum(max(0.0, l["sobra"]) for l in futuros))))

        return html.Div([
            html.Div(resumo, className="pop-resumo"),
            html.Div([
                html.Span("realizado", className="leg-item realizado"),
                html.Span("previsto", className="leg-item previsto"),
                html.Span("entra", className="leg-item entra"),
                html.Span("sai", className="leg-item sai"),
            ], className="ano-legenda"),
            html.Div(colunas, className="ano-colunas"),
            html.Div([
                html.Div([
                    html.Div(l["rotulo"] + "/" + l["mes"][:4], className="ano-linha-mes"),
                    html.Div("entra R$ " + brl(l["entrada"]), className="ano-linha-v"),
                    html.Div("sai R$ " + brl(l["saida"]), className="ano-linha-v"),
                    html.Div("parcelas R$ " + brl(l["parcelas"]), className="ano-linha-v"),
                    html.Div("R$ " + brl(l["sobra"]),
                             className="ano-linha-v forte " +
                                       ("pos" if l["sobra"] >= 0 else "neg")),
                    html.Div("sem lancamento" if l["sem_dados"] else
                             "fechado" if l["fechado"] else
                             ("mes corrente" if l["realizado"] else "previsto"),
                             className="ano-linha-tag"),
                ], className="ano-linha " + _classe_mes(l))
                for l in linhas
            ], className="ano-tabela"),
            html.Div("Mes fechado mostra o que foi lancado de verdade. Mes futuro usa a "
                     "projecao: renda base, contas por vencimento e a fatura com as "
                     "parcelas que ainda estiverem correndo.", className="pop-nota"),
        ])

    def meses_disponiveis(est):
        """Meses com movimento no banco, para o seletor. Sempre inclui o atual."""
        with conectar(db_path) as con:
            achados = {r[0] for r in con.execute(
                "SELECT substr(vencimento,1,7) FROM contas_a_pagar "
                "UNION SELECT mes_ref FROM gastos_fatura "
                "UNION SELECT mes FROM horas_receber") if r[0]}
        achados.add(est["mes"])
        return sorted(x for x in achados if len(x) == 7)

    def painel_executivo(est, escala):
        """Visao executiva: os poucos numeros que decidem o mes (ou o ano)."""
        if escala == "ano":
            fluxo = fluxo_calendario(db_path, est["mes"][:4])
            ano = visao_anual(fluxo)[0]
            fechados = [l for l in fluxo if l["fechado"]]
            titulo = ("Ano de %s - %d meses fechados, %d previstos"
                      % (est["mes"][:4], len(fechados), 12 - len(fechados)))
            cartoes = [
                ("Entra no ano", "R$ " + brl(ano["entrada"]), "registros e previsões do ano", "bom"),
                ("Sai no ano", "R$ " + brl(ano["saida"]), "contas + faturas + variavel", "ruim"),
                ("Guarda no ano", "R$ " + brl(ano["aporte"]),
                 "soma dos meses com sobra", "bom" if ano["aporte"] > 0 else "ruim"),
                ("Meses no vermelho", str(sum(1 for l in fluxo if l["sobra"] < 0)),
                 "de %d meses do ano" % ano["meses"],
                 "ruim" if any(l["sobra"] < 0 for l in fluxo) else "bom"),
                ("Pico de parcelas", "R$ " + brl(max(l["parcelas"] for l in fluxo)),
                 "mes mais pesado do ano", "alerta"),
                ("Metas abertas", str(len([m for m in est["metas"] if m["falta"] > 0])),
                 est["fontes"]["metas"], "neutro"),
            ]
        else:
            titulo = "Mes de %s" % est["mes"]
            pct = (est["sobra"] / est["renda_mes"] * 100.0) if est["renda_mes"] else 0.0
            cartoes = [
                ("Renda do mes", "R$ " + brl(est["renda_mes"]),
                 ("recebido R$ %s · a receber R$ %s"
                  % (brl(est["renda_paga"], 0), brl(est["renda_pendente"], 0))), "bom"),
                ("Despesa do mes", "R$ " + brl(est["despesas_total"]),
                 "contas do mes mais as faturas fechadas", "ruim"),
                ("Sobra", "R$ " + brl(est["sobra"]),
                 "%.0f%% da renda sobra livre" % pct if est["sobra"] >= 0
                 else "o mes fecha %.0f%% no vermelho" % abs(pct),
                 "bom" if est["sobra"] >= 0 else "ruim"),
                ("Contas do mes", "R$ " + brl(est["fixas"]),
                 "boleto, conta e Pix - fora do cartao", "neutro"),
                ("Faturas dos cartoes", "R$ " + brl(est["total_faturas"]),
                 " · ".join("%s R$ %s" % (n.replace("Cartão ", ""), brl(f["total"], 0))
                            for n, f in sorted(est["faturas"].items())), "alerta"),
                ("Ainda a entrar", "R$ " + brl(est["a_receber"] + est["tk_aprovado"]),
                 "aprovado mais o pipeline de tickets", "alerta"),
            ]
        blocos = [
            html.Div(titulo, className="exec-titulo"),
            html.Div([kpi(*c) for c in cartoes], className="neu-kpis"),
        ]
        if escala == "ano":
            # No modo ano o painel deixa de ser so numeros: o grafico dos 12
            # meses vem para a pagina, senao a troca mes/ano nao muda nada que
            # se veja.
            blocos.append(html.Div([
                html.Button("← Ano anterior", id={"type": "mapa-ano-mover", "delta": -1}, n_clicks=0),
                html.Span(est["mes"][:4]),
                html.Button("Próximo ano →", id={"type": "mapa-ano-mover", "delta": 1}, n_clicks=0),
            ], className="canvas-year-nav"))
        return html.Div(blocos, className="painel-exec escala-%s" % escala)

    def grafico_ano(linhas):
        """Colunas dos 12 meses direto na pagina: realizado solido, previsto vazado."""
        teto = max([l["entrada"] for l in linhas] + [l["saida"] for l in linhas] + [1.0])
        return html.Div([
            html.Div([
                html.Span("realizado", className="leg-item realizado"),
                html.Span("previsto", className="leg-item previsto"),
                html.Span("entra", className="leg-item entra"),
                html.Span("sai", className="leg-item sai"),
            ], className="ano-legenda"),
            html.Div([
                html.Div([
                    html.Div([
                        html.Div(className="col-barra entra",
                                 style={"height": "%.1f%%" % (l["entrada"] / teto * 100.0)}),
                        html.Div(className="col-barra sai",
                                 style={"height": "%.1f%%" % (l["saida"] / teto * 100.0)}),
                    ], className="col-par"),
                    html.Div(l["rotulo"], className="col-mes"),
                    html.Div("sem dados" if l["sem_dados"] else "R$ " + brl(l["sobra"], 0),
                             className="col-sobra " + ("vazio" if l["sem_dados"]
                                                       else "pos" if l["sobra"] >= 0 else "neg")),
                ], className="col-ano " + _classe_mes(l),
                    title=("%s · sem lancamento de renda no banco" % l["mes"])
                          if l["sem_dados"] else
                          ("%s · entra R$ %s · sai R$ %s · sobra R$ %s"
                           % (l["mes"], brl(l["entrada"]), brl(l["saida"]), brl(l["sobra"]))))
                for l in linhas
            ], className="ano-colunas palco-3d"),
        ], className="neu-graf")

    def bloco_discussao(no_id):
        linhas = agentes.thread(db_path, no_id)
        month = mes_do_no(no_id)
        if month:
            # Legacy discussions retain their IDs and remain visible in their original month.
            legacy_id = no_id.split("::", 1)[1]
            with conectar(db_path) as con:
                legacy = [dict(r) for r in con.execute(
                    "SELECT * FROM arvore_discussoes WHERE no_id=? ORDER BY id DESC", (legacy_id,))]
            for row in legacy:
                try:
                    if json.loads(row.get("contexto") or "{}").get("mes") == month:
                        linhas.append(row)
                except (ValueError, TypeError):
                    continue
            linhas.sort(key=lambda row: row["id"], reverse=True)
        if not linhas:
            return html.Div("Nenhuma discussao aberta neste caminho ainda.",
                            className="pop-vazio")
        cartoes = []
        for l in linhas:
            if l["status"] == "respondido":
                corpo, classe = l["resposta"], "ok"
            elif l["resposta"]:
                corpo, classe = l["resposta"], "erro"
            else:
                corpo, classe = "Aguardando o agente responder...", "espera"
            cartoes.append(html.Div([
                html.Div([
                    html.Span(l["agente"], className="disc-agente"),
                    html.Span(l["papel"], className="disc-papel"),
                    html.Span(l["criado"][5:16].replace("T", " "), className="disc-data"),
                ], className="disc-cab"),
                html.Div("voce: " + l["motivo"], className="disc-motivo"),
                html.Div(corpo, className="disc-corpo " + classe),
            ], className="neu-disc"))
        return html.Div(cartoes, className="disc-lista")

    def modal_vazio():
        return dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="mapa-modal-titulo")),
            dbc.ModalBody([
                html.Div(id="mapa-modal-topo", className="pop-topo"),
                html.Div(id="mapa-modal-req"),
                dbc.Tabs([
                    dbc.Tab(html.Div(id="mapa-modal-fluxo", className="pop-aba"),
                            label="Fluxo mes a mes", tab_id="aba-fluxo"),
                    dbc.Tab(html.Div(id="mapa-modal-ano", className="pop-aba"),
                            label="Visao por ano", tab_id="aba-ano"),
                ], id="mapa-abas", active_tab="aba-fluxo", className="pop-abas"),
                html.Div([
                    html.H6("Quero seguir por este caminho", className="pop-h"),
                    html.P("Escreva o motivo. Isso registra o passo e abre a discussao "
                           "com os agentes responsaveis por essa area.", className="pop-lead"),
                    dbc.Textarea(id="mapa-motivo", rows=3, maxLength=2000,
                                 placeholder="Por que este caminho agora? O que precisa se "
                                             "manter verdadeiro para ele funcionar?"),
                    html.Div([
                        dbc.Button("Seguir este caminho", id="mapa-seguir",
                                   n_clicks=0, className="btn-seguir"),
                        dbc.Button("Reconsultar agentes", id="mapa-reconsultar",
                                   n_clicks=0, color="secondary", outline=True,
                                   className="btn-reconsultar"),
                    ], className="pop-acoes"),
                    html.Div(id="mapa-aviso", className="pop-aviso"),
                ], className="neu-acao"),
                html.Div([
                    html.H6("Discussao com os agentes", className="pop-h"),
                    html.Div(id="mapa-discussao"),
                ]),
            ]),
        ], id="mapa-modal", is_open=False, size="xl", scrollable=True,
            className="mapa-modal", contentClassName="neu-modal")

    def conteudo_modal(no, est):
        topo = html.Div([
            html.Div([html.Div(no["sub"], className="pop-sub"),
                      html.Div(no["valor"], className="pop-valor st-%s" % no["status"])]),
            html.Div(no.get("nota", ""), className="pop-nota-topo"),
        ])
        return (no["rotulo"], topo, bloco_requisitos(no), bloco_fluxo(no, est),
                bloco_ano(no, est), bloco_discussao(no["id"]))

    def achar(nos, no_id):
        return next((n for n in nos if n["id"] == no_id), None)

    # ---------------- pagina ----------------
    def montar(mes=None, escala="mes"):
        est = estado(db_path, mes)
        if escala == "ano":
            year = est["mes"][:4]
            return html.Div([
                painel_executivo(est, escala),
                html.P("Doze meses, cada um com seu fluxo. Abra um mês para explorar suas decisões. "
                       "Previsões usam a renda base e as regras atuais do painel; registros não são projeções.",
                       className="canvas-explainer"),
                annual_board(fluxo_calendario(db_path, year), year),
            ], className="mapa-pagina")
        nos = gerar_mensal(est)
        mudou, eventos, trilha = sincronizar(db_path, est, nos)
        ids = {n["id"] for n in nos}

        # Passos antigos que nao existem no mapa atual sao ignorados: o agente
        # refez a arvore e aquele ramo pode ter deixado de fazer sentido.
        percorridos = [t["no_id"] for t in trilha if t["no_id"] in ids]
        raiz = est["mes"] + "::raiz"
        atual = percorridos[-1] if percorridos else raiz
        ativos = set(percorridos) | {raiz}
        # A "curva": filhos diretos do no onde voce parou. E a decisao que esta
        # acontecendo agora - nem trilha andada, nem alternativa distante.
        curvas = {n["id"] for n in nos if n["pai"] == atual}

        def classe(n):
            if n["id"] == atual:
                return "atual"
            if n["id"] in ativos:
                return "percorrido"
            if n["id"] in curvas:
                return "curva"
            return "aberto"

        largura, altura = dimensoes(nos)
        ligacoes = [
            html.Div(className=a["classe"] + (" lado-%s" % a["lado"] if a["lado"] else ""),
                     style={"left": "%.1fpx" % a["left"], "top": "%.1fpx" % a["top"],
                            "width": "%.1fpx" % a["width"], "height": "%.1fpx" % a["height"]})
            for a in conectores(nos, ativos | curvas)
        ]

        painel = painel_executivo(est, escala)

        linha_trilha = html.Div(
            [html.Span("Voce esta aqui", className="trilha-label")] +
            ([html.Span("inicio do mapa", className="trilha-item")] if not percorridos else
             [html.Span(t["rotulo"], className="trilha-item")
              for t in trilha if t["no_id"] in ids]),
            className="trilha-linha",
        )

        pend = agentes.pendentes(db_path)
        log = html.Div([
            html.Div(
                "Mapa refeito agora: movimentacao detectada." if mudou
                else "Sem movimentacao nova desde o ultimo tracado.",
                className="mapa-sinal " + ("on" if mudou else "off"),
            ),
            html.Div("%d consulta(s) a agentes aguardando o 9Router." % pend,
                     className="mapa-sinal off") if pend else None,
            html.Div([
                html.Div([
                    html.Span(e["criado"][5:16].replace("T", " "), className="ev-data"),
                    html.Span(e["texto"], className="ev-txt"),
                ], className="ev ev-%s" % e["tipo"]) for e in eventos
            ], className="ev-lista"),
        ], className="neu-log")

        # Assim que voce anda pelo menos um passo, o resto do mapa recua.
        marca = " tem-trilha" if percorridos else ""
        palco = html.Div([
            html.Div(ligacoes, className="mapa-ligacoes" + marca),
            html.Div([cartao_no(n, classe(n)) for n in nos], className="mapa-nos" + marca),
        ], className="mapa-palco", style={"width": "%dpx" % largura, "height": "%dpx" % altura})

        # O fundo em parallax vive no body (mapa-parallax.js). Ter uma copia
        # aqui dentro cobria o cabecalho: era um `position:fixed` declarado
        # depois dele no DOM.
        return html.Div([
            painel,
            linha_trilha,
            html.P("Planejamento de " + est["mes"] + ". " +
                     ("Renda calculada com os valores recebidos e pendentes deste mês."
                      if est["renda_paga"] > 0 else "Renda estimada com o salário base e os valores pendentes deste mês."),
                     className="canvas-explainer"),
            viewport(palco, "mes:" + est["mes"], "Decisões · " + est["mes"]),
            log,
        ], className="mapa-pagina")

    def page(mes=None):
        if not is_authed():
            return html.Div()
        est = estado(db_path, mes)
        # Os controles ficam FORA de mapa-corpo: se vivessem dentro, cada
        # redesenho os recriaria e o seletor perderia o foco no meio do clique.
        cabecalho = html.Div([
            html.Div([
                html.Div("MAPA FINANCEIRO", className="mapa-eyebrow"),
                html.H2("Seu próximo passo, mês a mês"),
                html.P("Todo numero vem do seu banco, na mesma conta do resto do painel. "
                       "Explore o ano ou abra uma decisão para ver o que ela exige.", className="mapa-lead"),
            ]),
            html.Div([
                html.Div(id="mapa-mes-eco", className="exec-eco"),
                dbc.RadioItems(id="mapa-escala", value="mes", inline=True, persistence=True, persistence_type="session",
                               options=[{"label": "Mes", "value": "mes"},
                                        {"label": "Ano", "value": "ano"}],
                               className="exec-escala"),
            ], className="exec-controles"),
        ], className="mapa-hero")

        return dbc.Container([
            dcc.Interval(id="mapa-tick", interval=45000, n_intervals=0),
            dcc.Store(id="mapa-no-sel"),
            cabecalho,
            html.Div(id="mapa-corpo", children=montar(est["mes"], "mes")),
            modal_vazio(),
        ], fluid=True, className="mapa-container")

    # ---------------- callbacks ----------------
    @app.callback(
        Output("mapa-corpo", "children"),
        Output("mapa-mes-eco", "children"),
        Input("mapa-tick", "n_intervals"),
        # O mes vem do navegador da topbar: as setas < > passam a mover o mapa
        # junto com o resto do painel, em vez de cada tela ter o seu proprio mes.
        Input("mes-sel-v3", "data"),
        Input("mapa-escala", "value"),
    )
    def readaptar(_tick, mes, escala):
        """So redesenha. Andar no mapa virou acao explicita dentro do pop-up."""
        if not is_authed():
            return html.Div(), ""
        mes = mes or None
        eco = "Mapa em %s" % (mes or "mes atual")
        return montar(mes, escala), eco

    @app.callback(
        Output("mes-sel-v3", "data", allow_duplicate=True),
        Output("mapa-escala", "value"),
        Input({"type": "mapa-mes-abrir", "mes": ALL}, "n_clicks"),
        Input({"type": "mapa-ano-mover", "delta": ALL}, "n_clicks"),
        State("mes-sel-v3", "data"),
        prevent_initial_call=True,
    )
    def navegar_canvas(month_clicks, year_clicks, month):
        trigger = ctx.triggered_id
        if not is_authed() or not isinstance(trigger, dict):
            return no_update, no_update
        if trigger.get("type") == "mapa-mes-abrir" and any(month_clicks or []):
            return trigger["mes"], "mes"
        if trigger.get("type") == "mapa-ano-mover" and any(year_clicks or []):
            month = month or estado(db_path)["mes"]
            return str(int(month[:4]) + int(trigger["delta"])) + month[4:], "ano"
        return no_update, no_update

    @app.callback(
        Output("mapa-modal", "is_open"),
        Output("mapa-no-sel", "data"),
        Output("mapa-modal-titulo", "children"),
        Output("mapa-modal-topo", "children"),
        Output("mapa-modal-req", "children"),
        Output("mapa-modal-fluxo", "children"),
        Output("mapa-modal-ano", "children"),
        Output("mapa-discussao", "children"),
        Output("mapa-motivo", "value"),
        Output("mapa-aviso", "children"),
        Input({"type": "mapa-no", "id": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def abrir_pop(cliques):
        gatilho = ctx.triggered_id
        # Redesenhar o mapa recria os nos com n_clicks=0; sem esta guarda o
        # pop-up abriria sozinho a cada readaptacao.
        if not is_authed() or not isinstance(gatilho, dict) or not any(c for c in cliques or []):
            return (no_update,) * 10
        month = mes_do_no(gatilho.get("id"))
        if not month:
            return (no_update,) * 10
        est = estado(db_path, month)
        no = achar(gerar_mensal(est), gatilho["id"])
        if not no:
            return (no_update,) * 10
        titulo, topo, req, fluxo, ano, disc = conteudo_modal(no, est)
        return True, no["id"], titulo, topo, req, fluxo, ano, disc, "", ""

    @app.callback(
        Output("mapa-discussao", "children", allow_duplicate=True),
        Output("mapa-aviso", "children", allow_duplicate=True),
        Output("mapa-corpo", "children", allow_duplicate=True),
        Output("mapa-motivo", "value", allow_duplicate=True),
        Input("mapa-seguir", "n_clicks"),
        Input("mapa-reconsultar", "n_clicks"),
        State("mapa-no-sel", "data"),
        State("mapa-motivo", "value"),
        State("mes-sel-v3", "data"),
        State("mapa-escala", "value"),
        prevent_initial_call=True,
    )
    def agir(_seguir, _reconsultar, no_id, motivo, mes, escala):
        if not is_authed() or not mes_do_no(no_id):
            return no_update, no_update, no_update, no_update

        if ctx.triggered_id == "mapa-reconsultar":
            n = agentes.reconsultar(db_path, no_id)
            aviso = ("Reenviado para %d agente(s). A resposta aparece aqui." % n) if n \
                    else "Nada pendente neste caminho."
            return bloco_discussao(no_id), aviso, no_update, no_update

        est = estado(db_path, mes_do_no(no_id))
        no = achar(gerar_mensal(est), no_id)
        if not no:
            return no_update, "Esse ramo saiu do mapa na ultima readaptacao.", montar(mes, escala), no_update

        contexto = {
            "mes": est["mes"], "renda_do_mes": est["renda_mes"],
            "contas_nao_cartao": est["fixas"],
            "faturas": {n: f["total"] for n, f in est["faturas"].items()},
            "despesa_total": est["despesas_total"], "sobra": est["sobra"],
            "a_receber": est["a_receber"], "pipeline_tickets": est["tk_aprovado"],
            "horas_trabalhadas": est["horas_trabalhadas"], "horas_base": est["horas_base"],
            "caminho": no["rotulo"], "o_que_exige": no["requisitos"], "efeito": no["valor"],
        }
        try:
            ids = agentes.abrir(db_path, no, motivo, contexto)
        except ValueError as exc:
            return no_update, str(exc), no_update, no_update

        seguiu = andar(db_path, no["id"], no["rotulo"], est["fingerprint"])
        agentes.disparar(db_path, ids)
        aviso = ("Passo registrado e %d agente(s) consultados." % len(ids)) if seguiu else \
                "Passo desfeito; os agentes foram consultados assim mesmo."
        return bloco_discussao(no_id), aviso, montar(mes, escala), ""

    return page
