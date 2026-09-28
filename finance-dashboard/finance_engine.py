#!/usr/bin/env python3
"""Estado financeiro real, derivado 100% do banco. Nenhum numero fixo aqui.

A definicao de despesa e a MESMA do resto do dashboard (app.py):

    despesa do mes = contas_a_pagar do mes que NAO sao de cartao
                   + fatura liquida de cada cartao ativo

A fatura liquida do mes corrente e o valor fechado que voce registrou no
config; nos meses seguintes ela e projetada por parcelas + assinaturas.
Somar parcela e assinatura por fora da fatura conta o mesmo dinheiro duas
vezes - foi exatamente isso que fazia os numeros nao baterem.

Cada valor exposto carrega a origem (tabela + filtro) em `fontes`.
"""
import hashlib
from contextlib import contextmanager
import json
import sqlite3
from datetime import date, datetime

# Faturas fechadas do mes corrente: mesmos defaults que o app.py usa quando a
# chave nao esta no config.
FATURA_FECHADA = {}

FILTRO_NAO_CARTAO = ("(cartao LIKE '%Conta%' OR cartao LIKE '%Pix%' OR cartao IS NULL)")


@contextmanager
def conectar(db_path):
    con = sqlite3.connect(db_path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def mes_corrente():
    return date.today().strftime("%Y-%m")


def _n(v):
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return 0.0
    return f if f == f and abs(f) != float("inf") else 0.0


def _um(con, sql, params=()):
    row = con.execute(sql, params).fetchone()
    return _n(row[0]) if row else 0.0


def _cfg(con):
    return {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM config")}


def _mes_somar(mes, n):
    ano, m = int(mes[:4]), int(mes[5:7])
    total = (ano * 12 + m - 1) + n
    return "%04d-%02d" % (total // 12, total % 12 + 1)


def mes_offset(mes, ref=None):
    """Quantos meses `mes` esta a frente do mes corrente (pode ser negativo)."""
    ref = ref or mes_corrente()
    return (int(mes[:4]) * 12 + int(mes[5:7])) - (int(ref[:4]) * 12 + int(ref[5:7]))


def parcela_no_mes(parcela_atual, parcela_total, mes, ref=None):
    """Numero da parcela cobrada em `mes`, ou None se nao e cobrada nesse mes.

    `parcela_atual` e a parcela do MES CORRENTE, 1-indexada. Logo `0/1` ainda
    nao comecou a ser cobrada e `10/10` esta sendo cobrada agora - o oposto do
    que "quantas ja paguei" sugeriria.
    """
    n = int(_n(parcela_atual)) + mes_offset(mes, ref)
    return n if 1 <= n <= int(_n(parcela_total)) else None


def _meses_entre(mes, alvo_iso):
    """Meses cheios de `mes` ate a data alvo. None se a data for invalida."""
    if not alvo_iso:
        return None
    try:
        alvo = datetime.fromisoformat(str(alvo_iso)[:10]).date()
    except ValueError:
        return None
    return (alvo.year * 12 + alvo.month) - (int(mes[:4]) * 12 + int(mes[5:7]))


def brl(v, casas=2):
    return format(float(v or 0), ",.%df" % casas).replace(",", "_").replace(".", ",").replace("_", ".")


def faturas_do_mes(con, cfg, mes, cortes=(), ref=None):
    """Fatura liquida de cada cartao ativo, na mesma regra do app.py.

    `cortes` sao ids de assinatura cancelados. Eles nao mexem na fatura ja
    fechada do mes corrente - cancelar hoje so alivia o mes que vem.
    """
    cortes = set(cortes)
    cartoes = [r["nome"] for r in con.execute(
        "SELECT nome FROM cartoes_credito WHERE ativo=1")]
    fat = {nome: {"parcelas": 0.0, "assinaturas": 0.0, "credito": 0.0, "total": 0.0}
           for nome in cartoes}

    for r in con.execute("SELECT categoria cartao, valor_parcela, parcela_atual, "
                         "parcela_total FROM compras_parceladas"):
        if parcela_no_mes(r["parcela_atual"], r["parcela_total"], mes, ref) is None:
            continue
        nome = str(r["cartao"] or "").strip()
        if nome in fat:
            fat[nome]["parcelas"] += _n(r["valor_parcela"])

    for r in con.execute("SELECT id, cartao, valor FROM assinaturas WHERE ativa=1 "
                         "AND cartao IS NOT NULL AND cartao<>'' AND cartao<>'Conta'"):
        nome = str(r["cartao"] or "").strip()
        if nome in fat and r["id"] not in cortes:
            fat[nome]["assinaturas"] += _n(r["valor"])

    if mes_offset(mes, ref) == 0:
        # Mes corrente: vale o que a fatura fechou de verdade.
        closed = {r["cartao"]: r["valor"] for r in con.execute("SELECT cartao, valor FROM faturas_fechadas WHERE mes=?", (mes,))}
        for nome, valor in closed.items():
            if nome not in fat:
                continue
            fechada = _n(valor)
            bruto = fat[nome]["parcelas"] + fat[nome]["assinaturas"]
            fat[nome]["credito"] = max(0.0, round(bruto - fechada, 2))
            fat[nome]["total"] = fechada
        for nome in fat:
            if nome not in closed:
                fat[nome]["total"] = fat[nome]["parcelas"] + fat[nome]["assinaturas"]
    else:
        for f in fat.values():
            f["total"] = f["parcelas"] + f["assinaturas"] - f["credito"]

    return fat


def estado(db_path, mes=None):
    """Fotografia do mes: renda, despesas, sobra, metas, alavancas e fingerprint."""
    mes = mes or mes_corrente()
    with conectar(db_path) as con:
        cfg = _cfg(con)
        fontes = {}

        # --- RENDA -------------------------------------------------------
        renda_base = _n(cfg.get("salario") or cfg.get("salario_base") or cfg.get("renda_mensal"))
        horas_base = _n(cfg.get("horas_base_mes") or cfg.get("horas_base_total")) or 0.0
        valor_hora = _n(cfg.get("valor_hora_extra")) or 0.0

        pagos = _um(con, "SELECT SUM(valor) FROM horas_receber WHERE mes=? AND status='Pago'", (mes,))
        pendentes = _um(con, "SELECT SUM(valor) FROM horas_receber WHERE mes=? AND status='Pendente'", (mes,))
        # Mesma regra do app: sem nada recebido, o salario base entra como projecao.
        renda_mes = (pagos + pendentes) if pagos > 0 else (renda_base + pendentes)
        fontes["renda_mes"] = "o que foi pago e o que ainda falta receber no mes"
        fontes["renda_base"] = "salario base do mes"

        horas_mes = con.execute(
            "SELECT total_hours FROM horas_mensal WHERE mes=?", (mes,)).fetchone()
        horas_trabalhadas = _n(horas_mes["total_hours"]) if horas_mes else 0.0
        fontes["horas_trabalhadas"] = "horas lancadas no mes"
        horas_excedentes = max(0.0, horas_trabalhadas - horas_base)

        a_receber = _um(con, "SELECT SUM(valor) FROM horas_receber WHERE status!='Pago'")
        fontes["a_receber"] = "horas aprovadas que ainda nao caíram"

        tk_aprovado = _um(con, "SELECT SUM(valor) FROM tickets_pagamento "
                               "WHERE status_pgto='PENDENTE' AND valor>0")
        tk_horas_aprovadas = _um(con, "SELECT SUM(horas) FROM tickets_pagamento "
                                      "WHERE status_pgto='PENDENTE' AND valor>0")
        fontes["tk_aprovado"] = "tickets com valor estimado e ainda nao pagos"

        tk_travados = [
            {"cliente": r["cliente"], "qtd": int(r["n"])}
            for r in con.execute(
                "SELECT cliente, COUNT(*) n FROM tickets_pagamento "
                "WHERE status_pgto='PENDENTE' AND (valor IS NULL OR valor=0) "
                "GROUP BY cliente ORDER BY n DESC")
        ]
        fontes["tk_travados"] = "tickets parados, sem estimativa e sem pagamento"

        # --- DESPESAS (mesma definicao do app.py) ------------------------
        fixas = _um(con, "SELECT SUM(valor) FROM contas_a_pagar WHERE " + FILTRO_NAO_CARTAO +
                         " AND substr(vencimento,1,7)=?", (mes,))
        fontes["fixas"] = "contas do mes pagas por boleto, conta ou Pix"

        faturas = faturas_do_mes(con, cfg, mes)
        total_faturas = sum(f["total"] for f in faturas.values())
        fontes["faturas"] = ("fatura fechada do config no mes corrente; "
                             "parcelas + assinaturas nos meses seguintes")

        despesas_total = fixas + total_faturas
        sobra = renda_mes - despesas_total

        assinaturas = [dict(r) for r in con.execute(
            "SELECT id, nome, valor, dia_do_mes, cartao FROM assinaturas "
            "WHERE ativa=1 ORDER BY valor DESC")]
        total_assinaturas = sum(_n(a["valor"]) for a in assinaturas)
        fontes["assinaturas"] = "assinaturas ativas hoje"

        # Parcelas que estao sendo cobradas NESTE mes, pela regra oficial.
        parcelas = []
        for r in con.execute("SELECT id, descricao, categoria cartao, valor_parcela, "
                             "parcela_atual, parcela_total FROM compras_parceladas"):
            n = parcela_no_mes(r["parcela_atual"], r["parcela_total"], mes)
            if n is None:
                continue
            p = dict(r)
            p["parcela_do_mes"] = n
            p["restantes"] = int(_n(r["parcela_total"])) - n + 1
            parcelas.append(p)
        parcelas.sort(key=lambda p: p["restantes"])
        total_parcelas = sum(_n(p["valor_parcela"]) for p in parcelas)
        fontes["parcelas"] = "compras parceladas cobradas neste mes"

        variaveis = _um(con, "SELECT SUM(valor) FROM gastos_fatura WHERE mes_ref=?", (mes,))
        fontes["variaveis"] = "gastos lancados na fatura (ja embutidos nela)"

        # --- METAS E CAIXINHAS -------------------------------------------
        metas = []
        for r in con.execute("SELECT * FROM metas WHERE ativa=1 ORDER BY data_alvo"):
            alvo, atual = _n(r["valor_alvo"]), _n(r["valor_atual"])
            metas.append({
                "id": r["id"], "nome": r["nome"], "alvo": alvo, "atual": atual,
                "falta": max(0.0, alvo - atual), "data_alvo": r["data_alvo"],
                "prazo_meses": _meses_entre(mes, r["data_alvo"]),
            })
        fontes["metas"] = "suas metas ativas"

        caixinhas = []
        for r in con.execute("SELECT id, nome, meta FROM caixinhas"):
            caixinhas.append({
                "id": r["id"], "nome": r["nome"], "meta": _n(r["meta"]),
                "saldo": _um(con, "SELECT SUM(valor) FROM caixinhas_movimentos "
                                  "WHERE caixinha_id=? AND tipo!='projecao'", (r["id"],)),
            })
        fontes["caixinhas"] = "saldo real das caixinhas"

        moradia = [dict(r) for r in con.execute("SELECT * FROM moradia ORDER BY total_mensal")]

        # --- FINGERPRINT --------------------------------------------------
        marcadores = [
            _um(con, "SELECT COALESCE(MAX(id),0) FROM contas_a_pagar"),
            _um(con, "SELECT COALESCE(SUM(valor),0) FROM contas_a_pagar"),
            _um(con, "SELECT COALESCE(MAX(id),0) FROM gastos_fatura"),
            _um(con, "SELECT COALESCE(SUM(valor),0) FROM gastos_fatura"),
            _um(con, "SELECT COALESCE(MAX(id),0) FROM tickets_pagamento"),
            _um(con, "SELECT COALESCE(SUM(valor),0) FROM tickets_pagamento"),
            _um(con, "SELECT COALESCE(SUM(horas),0) FROM tickets_pagamento"),
            _um(con, "SELECT COALESCE(MAX(id),0) FROM horas_receber"),
            _um(con, "SELECT COALESCE(SUM(valor),0) FROM horas_receber"),
            _um(con, "SELECT COALESCE(SUM(total_hours),0) FROM horas_mensal"),
            _um(con, "SELECT COALESCE(SUM(valor_parcela),0) FROM compras_parceladas"),
            _um(con, "SELECT COALESCE(SUM(parcela_atual),0) FROM compras_parceladas"),
            _um(con, "SELECT COALESCE(SUM(valor),0) FROM assinaturas WHERE ativa=1"),
            _um(con, "SELECT COALESCE(SUM(valor_atual),0) FROM metas"),
            _um(con, "SELECT COALESCE(MAX(id),0) FROM caixinhas_movimentos"),
            round(total_faturas, 2),
        ]

    fp = hashlib.sha256(json.dumps([mes] + marcadores, sort_keys=True).encode()).hexdigest()[:16]

    return {
        "db": db_path,
        "mes": mes,
        "renda_base": renda_base,
        "renda_mes": renda_mes,
        "renda_paga": pagos,
        "renda_pendente": pendentes,
        "horas_base": horas_base,
        "valor_hora": valor_hora,
        "horas_trabalhadas": horas_trabalhadas,
        "horas_excedentes": horas_excedentes,
        "a_receber": a_receber,
        "tk_aprovado": tk_aprovado,
        "tk_horas_aprovadas": tk_horas_aprovadas,
        "tk_travados": tk_travados,
        "fixas": fixas,
        "faturas": faturas,
        "total_faturas": total_faturas,
        "assinaturas": assinaturas,
        "total_assinaturas": total_assinaturas,
        "parcelas": parcelas,
        "total_parcelas": total_parcelas,
        "variaveis": variaveis,
        "despesas_total": despesas_total,
        "sobra": sobra,
        "metas": metas,
        "caixinhas": caixinhas,
        "moradia": moradia,
        "fingerprint": fp,
        "fontes": fontes,
    }


def alavancas(est):
    """Acoes reais disponiveis, cada uma com impacto em R$ vindo do banco."""
    out = []
    va = est["valor_hora"]

    if est["sobra"] > 0:
        out.append({
            "id": "sobra", "rotulo": "Direcionar a sobra do mes",
            "detalhe": "Sobra apurada de R$ %s" % brl(est["sobra"]),
            "mensal": round(est["sobra"], 2), "pontual": 0.0, "tipo": "recorrente",
            "risco": "baixo", "fonte": "renda do mes - despesa do mes",
        })

    if est["a_receber"] > 0:
        out.append({
            "id": "receber", "rotulo": "Cobrar o que ja foi aprovado",
            "detalhe": "R$ %s lancados e ainda nao pagos" % brl(est["a_receber"]),
            "mensal": 0.0, "pontual": round(est["a_receber"], 2), "tipo": "pontual",
            "risco": "baixo", "fonte": est["fontes"]["a_receber"],
        })

    if est["tk_aprovado"] > 0:
        out.append({
            "id": "tickets", "rotulo": "Faturar o pipeline de tickets",
            "detalhe": "%.0fh estimadas em tickets nao pagos" % est["tk_horas_aprovadas"],
            "mensal": 0.0, "pontual": round(est["tk_aprovado"], 2), "tipo": "pontual",
            "risco": "medio", "fonte": est["fontes"]["tk_aprovado"],
        })

    travados = sum(t["qtd"] for t in est["tk_travados"])
    if travados:
        detalhe = ", ".join("%s (%d)" % (t["cliente"], t["qtd"]) for t in est["tk_travados"][:3])
        out.append({
            "id": "destravar", "rotulo": "Destravar %d tickets parados" % travados,
            "detalhe": "%s - estimativa de 2h por ticket" % detalhe,
            "mensal": 0.0, "pontual": round(travados * 2.0 * va, 2), "tipo": "pontual",
            "risco": "alto", "fonte": est["fontes"]["tk_travados"],
        })

    for a in est["assinaturas"][:4]:
        out.append({
            "id": "corte:%s" % a["id"], "rotulo": "Cancelar %s" % a["nome"],
            "detalhe": "R$ %s/mes no %s - alivia a partir do proximo mes"
                       % (brl(a["valor"]), a["cartao"] or "conta"),
            "mensal": round(_n(a["valor"]), 2), "pontual": 0.0, "tipo": "recorrente",
            "risco": "baixo", "fonte": est["fontes"]["assinaturas"],
        })

    for p in est["parcelas"][:3]:
        out.append({
            "id": "parcela:%s" % p["id"], "rotulo": "Fim de %s" % p["descricao"],
            "detalhe": "libera R$ %s/mes em %d meses (%d de %d)"
                       % (brl(p["valor_parcela"]), p["restantes"],
                          p["parcela_do_mes"], int(_n(p["parcela_total"]))),
            "mensal": round(_n(p["valor_parcela"]), 2), "pontual": 0.0,
            "tipo": "recorrente", "atraso_meses": p["restantes"],
            "risco": "baixo", "fonte": est["fontes"]["parcelas"],
        })

    for horas in (10, 20):
        out.append({
            "id": "horas:%d" % horas, "rotulo": "+%dh extras por mes" % horas,
            "detalhe": "%dh x R$ %s acima das %.0fh da base" % (horas, brl(va), est["horas_base"]),
            "mensal": round(horas * va, 2), "pontual": 0.0, "tipo": "recorrente",
            "risco": "medio" if horas <= 10 else "alto",
            "fonte": "seu valor por hora aplicado acima da base contratada",
        })

    return out


def projetar(falta, mensal, pontual=0.0, atraso_meses=0):
    """Meses ate fechar a lacuna. None quando nao fecha com a capacidade atual."""
    restante = max(0.0, falta - pontual)
    if restante <= 0:
        return 0
    if mensal <= 0:
        return None
    return atraso_meses + int(-(-restante // mensal))


def _mediana(valores):
    v = sorted(valores)
    if not v:
        return 0.0
    meio = len(v) // 2
    return v[meio] if len(v) % 2 else (v[meio - 1] + v[meio]) / 2.0


def calendario_fixas(db_path, mes, horizonte):
    """Contas nao-cartao, mes a mes, pelo vencimento real.

    Depois do ultimo mes lancado a projecao repete a mediana - que e o piso
    recorrente observado, nao um numero inventado.
    """
    with conectar(db_path) as con:
        linhas = {
            r["m"]: _n(r["v"]) for r in con.execute(
                "SELECT substr(vencimento,1,7) m, SUM(valor) v FROM contas_a_pagar "
                "WHERE " + FILTRO_NAO_CARTAO + " AND substr(vencimento,1,7) >= ? GROUP BY m",
                (mes,))
        }
    futuros = [v for k, v in linhas.items() if k > mes]
    recorrente = _mediana(futuros) if futuros else _mediana(list(linhas.values()))
    return [linhas.get(_mes_somar(mes, i), recorrente) for i in range(horizonte)]


def media_variaveis(db_path, mes):
    """Media dos gastos de fatura ja fechados. Mes corrente nao entra: incompleto."""
    with conectar(db_path) as con:
        valores = [_n(r["v"]) for r in con.execute(
            "SELECT mes_ref m, SUM(valor) v FROM gastos_fatura WHERE mes_ref < ? GROUP BY m",
            (mes,))]
    return sum(valores) / len(valores) if valores else 0.0


_cache_base = {}


def _base_projecao(db_path, est, horizonte, cortes):
    """Calendario e faturas de todos os meses do horizonte, calculados uma vez.

    O mapa projeta um fluxo por no (dezenas por tela). O fingerprint na chave
    faz o cache morrer sozinho assim que qualquer movimentacao acontece.
    """
    chave = (db_path, est["mes"], est["fingerprint"], horizonte, tuple(sorted(cortes)))
    if chave in _cache_base:
        return _cache_base[chave]
    if len(_cache_base) > 24:
        _cache_base.clear()
    fixas = calendario_fixas(db_path, est["mes"], horizonte)
    with conectar(db_path) as con:
        cfg = _cfg(con)
        faturas = [faturas_do_mes(con, cfg, _mes_somar(est["mes"], i), cortes)
                   for i in range(horizonte)]
    _cache_base[chave] = (fixas, faturas)
    return _cache_base[chave]


def fluxo_mensal(db_path, est, ajuste=None, horizonte=24):
    """Projeta mes a mes, com cada parcela morrendo na data certa.

    O mes 0 fecha exatamente com a despesa apurada; dos meses seguintes em
    diante entra tambem uma estimativa de gasto variavel (media dos meses ja
    fechados), que a fatura fechada do mes corrente ja embute.
    """
    ajuste = ajuste or {}
    extra_mensal = _n(ajuste.get("mensal"))
    pontual = _n(ajuste.get("pontual"))
    cortes = tuple(ajuste.get("cortes") or ())
    meta_falta = _n(ajuste.get("meta_falta"))

    fixas_cal, faturas_cal = _base_projecao(db_path, est, horizonte, cortes)
    variaveis_proj = media_variaveis(db_path, est["mes"])

    linhas, acumulado = [], 0.0
    for i in range(horizonte):
        fatura_i = sum(f["total"] for f in faturas_cal[i].values())
        if i == 0:
            entrada = est["renda_mes"] + extra_mensal + pontual
            fixas_i, variaveis_i = est["fixas"], 0.0
            fatura_i = est["total_faturas"]
        else:
            entrada = est["renda_base"] + extra_mensal
            fixas_i, variaveis_i = fixas_cal[i], variaveis_proj

        saida = fixas_i + fatura_i + variaveis_i
        sobra = entrada - saida
        aporte = max(0.0, sobra)
        acumulado += aporte
        linhas.append({
            "i": i, "mes": _mes_somar(est["mes"], i),
            "entrada": round(entrada, 2), "saida": round(saida, 2),
            "fixas": round(fixas_i, 2), "fatura": round(fatura_i, 2),
            "parcelas": round(sum(f["parcelas"] for f in faturas_cal[i].values()), 2),
            "variaveis": round(variaveis_i, 2),
            "sobra": round(sobra, 2), "aporte": round(aporte, 2),
            "acumulado": round(acumulado, 2),
            "pct": round(min(100.0, acumulado / meta_falta * 100.0), 1) if meta_falta > 0 else None,
            "fecha": bool(meta_falta > 0 and acumulado >= meta_falta),
        })
    return linhas


def fluxo_ano(db_path, est, ano=None, ajuste=None):
    """Os 12 meses do ano: o que ja aconteceu e o que ainda vai acontecer.

    Mes fechado usa o que foi lancado de verdade (renda recebida, contas do
    mes, fatura daquele mes). Mes futuro usa a projecao. Cada linha diz de
    qual lado esta em `realizado`, para o grafico nao misturar fato com
    previsao.
    """
    ajuste = ajuste or {}
    ano = ano or est["mes"][:4]
    cortes = tuple(ajuste.get("cortes") or ())
    extra_mensal = _n(ajuste.get("mensal"))
    corrente = mes_corrente()
    variaveis_proj = media_variaveis(db_path, est["mes"])

    linhas, acumulado = [], 0.0
    with conectar(db_path) as con:
        cfg = _cfg(con)
        for m in range(1, 13):
            mes = "%s-%02d" % (ano, m)
            passado = mes < corrente
            fat = faturas_do_mes(con, cfg, mes, cortes)
            fatura = sum(f["total"] for f in fat.values())
            fixas = _um(con, "SELECT SUM(valor) FROM contas_a_pagar WHERE " +
                             FILTRO_NAO_CARTAO + " AND substr(vencimento,1,7)=?", (mes,))

            if mes == est["mes"]:
                entrada, fixas, fatura = est["renda_mes"] + extra_mensal, est["fixas"], est["total_faturas"]
                variaveis = 0.0
            elif passado:
                # Mes fechado: vale o que entrou de verdade, sem estimativa.
                entrada = _um(con, "SELECT SUM(valor) FROM horas_receber "
                                   "WHERE mes=? AND status='Pago'", (mes,))
                variaveis = _um(con, "SELECT SUM(valor) FROM gastos_fatura WHERE mes_ref=?", (mes,))
            else:
                entrada = est["renda_base"] + extra_mensal
                variaveis = variaveis_proj

            saida = fixas + fatura + variaveis
            # Mes fechado sem nenhum lancamento de renda nao "fechou no
            # vermelho": ele simplesmente nao foi preenchido. Tratar os dois
            # como a mesma coisa inventaria um rombo que nunca existiu.
            sem_dados = bool(passado and entrada == 0)
            sobra = 0.0 if sem_dados else entrada - saida
            aporte = max(0.0, sobra)
            acumulado += aporte
            linhas.append({
                "mes": mes, "rotulo": "%02d" % m, "realizado": passado or mes == est["mes"],
                "fechado": passado, "sem_dados": sem_dados,
                "entrada": round(entrada, 2), "saida": round(saida, 2),
                "fixas": round(fixas, 2), "fatura": round(fatura, 2),
                "parcelas": round(sum(f["parcelas"] for f in fat.values()), 2),
                "variaveis": round(variaveis, 2),
                # `aporte` e o que sobra e pode ir para meta; visao_anual soma por ele.
                "sobra": round(sobra, 2), "aporte": round(aporte, 2),
                "acumulado": round(acumulado, 2), "pct": None, "fecha": False,
            })
    return linhas


def mes_que_fecha(fluxo):
    """Primeiro mes em que o acumulado alcanca a meta. None se nao alcanca."""
    for linha in fluxo:
        if linha["fecha"]:
            return linha
    return None


def visao_anual(fluxo):
    """Mesmo fluxo, agregado por ano civil."""
    anos = {}
    for linha in fluxo:
        a = anos.setdefault(linha["mes"][:4], {
            "ano": linha["mes"][:4], "meses": 0, "entrada": 0.0, "saida": 0.0,
            "sobra": 0.0, "aporte": 0.0, "acumulado": 0.0,
        })
        a["meses"] += 1
        for campo in ("entrada", "saida", "sobra", "aporte"):
            a[campo] += linha[campo]
        a["acumulado"] = linha["acumulado"]
    for a in anos.values():
        for campo in ("entrada", "saida", "sobra", "aporte"):
            a[campo] = round(a[campo], 2)
    return [anos[k] for k in sorted(anos)]
