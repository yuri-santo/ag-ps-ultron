#!/usr/bin/env python3
"""Graficos 3D em Matplotlib, no tema do painel.

Cada funcao devolve um `data:image/png;base64,...` pronto para `html.Img(src=...)`.

Limite honesto desta abordagem: a saida e IMAGEM. Nao tem hover com valor, nao
tem zoom e nao anima. Por isso todo grafico aqui desenha o valor em cima da
barra - sem isso o 3D vira enfeite ilegivel, porque a perspectiva distorce a
altura e as barras da frente escondem as de tras.
"""
import base64
import io
import math

import matplotlib
import numpy as np

matplotlib.use("Agg")  # sem servidor grafico: renderiza direto para memoria

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import colors as mcolors  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

# Mesma paleta do painel, para o PNG nao destoar do resto da tela.
FUNDO = "#232838"
TEXTO = "#e7ebf5"
FRACO = "#97a1b8"
GRADE = "#ffffff14"
VERDE = "#6fd2a8"
VERMELHO = "#e08296"
AZUL = "#8fd0e8"
AMBAR = "#e8bd7a"
ROXO = "#b6a3c3"
CICLO = [AZUL, VERDE, AMBAR, ROXO, VERMELHO, "#9fb6da"]

DPI = 110


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, facecolor=FUNDO,
                bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _eixo3d(largura, altura, titulo=None, elev=22, azim=-58):
    fig = plt.figure(figsize=(largura / DPI, altura / DPI), facecolor=FUNDO)
    ax = fig.add_subplot(111, projection="3d", facecolor=FUNDO)
    ax.view_init(elev=elev, azim=azim)
    # Os tres paineis do cubo recebem o fundo do painel; sem isso o Matplotlib
    # desenha caixas claras que brigam com o tema escuro.
    for eixo in (ax.xaxis, ax.yaxis, ax.zaxis):
        eixo.set_pane_color(mcolors.to_rgba(FUNDO, 1.0))
        eixo._axinfo["grid"]["color"] = GRADE
        eixo._axinfo["grid"]["linewidth"] = 0.6
        eixo.line.set_color(GRADE)
        eixo.label.set_color(FRACO)
    ax.tick_params(colors=FRACO, labelsize=7.5)
    if titulo:
        ax.set_title(titulo, color=TEXTO, fontsize=11, pad=12)
    return fig, ax


def _rotulo(v, casas=0):
    s = format(float(v or 0), ",.%df" % casas)
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def vazio(largura=760, altura=430, mensagem="sem dados"):
    """Placeholder no tema, para o painel nunca mostrar caixa clara."""
    fig = plt.figure(figsize=(largura / DPI, altura / DPI), facecolor=FUNDO)
    ax = fig.add_subplot(111, facecolor=FUNDO)
    ax.text(0.5, 0.5, mensagem, color=FRACO, fontsize=11, ha="center", va="center")
    ax.axis("off")
    return _png(fig)


def barras3d(rotulos, series, largura=760, altura=430, titulo=None,
             nomes=None, casas=0, unidade="R$"):
    """Barras 3D: cada serie vira uma fileira em profundidade.

    O valor vai escrito no topo de cada barra porque em 3D a altura sozinha
    nao se compara - a perspectiva encolhe o que esta no fundo.
    """
    if not rotulos or not series or not any(series):
        return vazio(largura, altura, "sem dados para o periodo")

    fig, ax = _eixo3d(largura, altura, titulo)
    n = len(rotulos)
    profundidade = len(series)
    larg_barra, prof_barra = 0.55, 0.42

    teto = max(max((float(v or 0) for v in s), default=0.0) for s in series) or 1.0
    for i, valores in enumerate(series):
        cor = CICLO[i % len(CICLO)]
        xs = list(range(n))
        # Valor negativo viraria barra atravessando o piso; o piso e zero.
        dz = [max(0.0, float(v or 0)) for v in valores]
        ax.bar3d(xs, [i] * n, [0] * n, larg_barra, prof_barra, dz,
                 color=cor, shade=True, alpha=0.94,
                 edgecolor=mcolors.to_rgba(TEXTO, 0.18), linewidth=0.4)
        for x, v in zip(xs, dz):
            if v <= 0:
                continue
            ax.text(x + larg_barra / 2, i + prof_barra / 2, v + teto * 0.03,
                    _rotulo(v, casas), color=TEXTO, fontsize=6.4,
                    ha="center", va="bottom", zorder=10)

    ax.set_xticks([x + larg_barra / 2 for x in range(n)])
    ax.set_xticklabels(rotulos, rotation=32, ha="right", fontsize=7)
    ax.set_yticks([i + prof_barra / 2 for i in range(profundidade)])
    ax.set_yticklabels(nomes or [""] * profundidade, fontsize=7.5)
    ax.set_zlim(0, teto * 1.18)
    ax.set_zlabel(unidade, fontsize=7.5)
    ax.set_box_aspect((max(2.0, n / 3.2), max(0.9, profundidade * 0.75), 1.1))
    return _png(fig)


def linha3d(rotulos, series, largura=760, altura=430, titulo=None,
            nomes=None, preencher=True):
    """Series temporais em 3D: cada serie corre numa profundidade propria."""
    if not rotulos or not series or not any(series):
        return vazio(largura, altura, "sem dados para o periodo")

    fig, ax = _eixo3d(largura, altura, titulo, elev=24, azim=-62)
    n = len(rotulos)
    xs = list(range(n))
    todos = [float(v or 0) for s in series for v in s] or [0.0]
    teto, piso = max(todos) or 1.0, min(min(todos), 0.0)

    for i, valores in enumerate(series):
        cor = CICLO[i % len(CICLO)]
        zs = [float(v or 0) for v in valores]
        ax.plot(xs, [i] * n, zs, color=cor, linewidth=2.4,
                marker="o", markersize=3.4, zorder=5)
        if preencher:
            # Parede sob a linha: da o volume que uma linha pura nao tem.
            verts = [[(x, i, piso) for x in xs] +
                     [(x, i, z) for x, z in zip(reversed(xs), reversed(zs))]]
            ax.add_collection3d(Poly3DCollection(verts, facecolor=cor, alpha=0.16))

    ax.set_xticks(xs)
    ax.set_xticklabels(rotulos, rotation=32, ha="right", fontsize=7)
    ax.set_yticks(list(range(len(series))))
    ax.set_yticklabels(nomes or [""] * len(series), fontsize=7.5)
    ax.set_zlim(piso * 1.1 if piso < 0 else 0, teto * 1.15)
    ax.set_box_aspect((max(2.0, n / 3.2), max(0.9, len(series) * 0.8), 1.0))
    return _png(fig)


def pizza3d(rotulos, valores, largura=520, altura=430, titulo=None, casas=0):
    """Rosca com espessura: a versao honesta de 'pizza 3D'.

    Pizza inclinada em perspectiva mente sobre as proporcoes - a fatia da
    frente parece maior que a de tras com o mesmo valor. Aqui a leitura
    continua sendo pelo angulo e a espessura e so volume.
    """
    valores = [max(0.0, float(v or 0)) for v in valores]
    if not valores or sum(valores) <= 0:
        return vazio(largura, altura, "sem dados para o periodo")

    fig = plt.figure(figsize=(largura / DPI, altura / DPI), facecolor=FUNDO)
    ax = fig.add_subplot(111, facecolor=FUNDO)
    total = sum(valores)
    cores = [CICLO[i % len(CICLO)] for i in range(len(valores))]

    ax.pie(valores, radius=1.0, startangle=90, counterclock=False,
           center=(0.0, -0.07),
           colors=[mcolors.to_rgba(c, 0.45) for c in cores],
           wedgeprops={"width": 0.42, "edgecolor": FUNDO, "linewidth": 1.2})
    fatias, _ = ax.pie(
        valores, radius=1.0, startangle=90, counterclock=False, colors=cores,
        wedgeprops={"width": 0.42, "edgecolor": FUNDO, "linewidth": 1.4})

    for fatia, rot, v in zip(fatias, rotulos, valores):
        ang = math.radians((fatia.theta1 + fatia.theta2) / 2.0)
        ax.text(1.24 * math.cos(ang), 1.24 * math.sin(ang),
                "%s\n%s (%.0f%%)" % (rot, _rotulo(v, casas), v / total * 100),
                color=TEXTO, fontsize=7.2, ha="center", va="center")

    ax.text(0, -0.07, _rotulo(total, casas), color=TEXTO, fontsize=13,
            ha="center", va="center", fontweight="bold")
    ax.set_xlim(-1.8, 1.8)
    ax.set_ylim(-1.8, 1.8)
    ax.set_aspect("equal")
    ax.axis("off")
    if titulo:
        ax.set_title(titulo, color=TEXTO, fontsize=11, pad=8)
    return _png(fig)


def superficie3d(x_rot, y_rot, matriz, largura=760, altura=430, titulo=None):
    """Superficie 3D para dados de duas dimensoes (mapa de calor com relevo)."""
    if not matriz or not matriz[0]:
        return vazio(largura, altura, "sem dados para o periodo")

    fig, ax = _eixo3d(largura, altura, titulo, elev=34, azim=-56)
    nx, ny = len(matriz[0]), len(matriz)
    # plot_surface so aceita array numpy - lista pura quebra em `Z.ndim`.
    xs = np.array([list(range(nx)) for _ in range(ny)], dtype=float)
    ys = np.array([[j] * nx for j in range(ny)], dtype=float)
    zs = np.array([[float(v or 0) for v in linha] for linha in matriz], dtype=float)

    ax.plot_surface(xs, ys, zs, cmap="viridis",
                    edgecolor=mcolors.to_rgba(TEXTO, 0.12), linewidth=0.3,
                    antialiased=True, alpha=0.95)
    ax.set_xticks(range(nx))
    ax.set_xticklabels(x_rot, rotation=32, ha="right", fontsize=7)
    ax.set_yticks(range(ny))
    ax.set_yticklabels(y_rot, fontsize=7)
    ax.set_box_aspect((max(2.0, nx / 3.0), max(1.0, ny / 3.0), 1.0))
    return _png(fig)
