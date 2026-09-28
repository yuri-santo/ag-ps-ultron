/* Parallax por velocidade de scroll.
 *
 * Aqui so publicamos o deslocamento bruto em --px / --py. Quem decide o quanto
 * cada camada anda e o CSS, via --sp. E a mesma ideia do Scroll Speed: uma
 * unica origem de movimento, velocidades diferentes por camada.
 *
 * O movimento horizontal vem do proprio palco do mapa (que rola no eixo X),
 * entao arrastar a arvore de lado tambem desloca o fundo - a arvore parece
 * estar na frente de um cenario, nao colada nele.
 */
(function () {
  "use strict";

  var parado = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (parado) return;

  var pendente = false;
  var px = 0;
  var py = 0;

  /* O fundo vive fora do conteudo do Dash, senao cada troca de pagina
   * destruiria e recriaria as camadas - e o parallax piscaria. */
  function garantirFundo() {
    var fundo = document.querySelector(".fundo-global");
    if (fundo) return fundo;
    fundo = document.createElement("div");
    fundo.className = "fundo-global";
    fundo.setAttribute("aria-hidden", "true");
    for (var i = 1; i <= 3; i++) {
      var camada = document.createElement("div");
      camada.className = "camada-g camada-g" + i;
      fundo.appendChild(camada);
    }
    document.body.insertBefore(fundo, document.body.firstChild);
    return fundo;
  }

  function aplicar() {
    pendente = false;
    var alvos = [garantirFundo(), document.querySelector(".mapa-fundo")];
    for (var i = 0; i < alvos.length; i++) {
      if (!alvos[i]) continue;
      alvos[i].style.setProperty("--px", px + "px");
      alvos[i].style.setProperty("--py", py + "px");
    }
  }

  function agendar() {
    if (pendente) return;
    pendente = true;
    window.requestAnimationFrame(aplicar);
  }

  window.addEventListener("scroll", function () {
    py = window.scrollY || window.pageYOffset || 0;
    agendar();
  }, { passive: true });

  // O palco e recriado a cada readaptacao do mapa, por isso o listener fica
  // delegado no document (fase de captura) em vez de preso ao elemento.
  document.addEventListener("scroll", function (ev) {
    var alvo = ev.target;
    if (alvo && alvo.classList && alvo.classList.contains("mapa-scroll")) {
      px = alvo.scrollLeft;
      agendar();
    }
  }, true);

  /* A arvore e maior que a janela nos dois eixos: a raiz fica na coluna da
   * esquerda mas na LINHA do meio, entao abrir no canto superior esquerdo
   * mostrava area vazia. O palco nasce centrado no no atual. */
  function centralizar() {
    var palco = document.querySelector(".mapa-scroll");
    if (!palco || palco.classList.contains("canvas-viewport") || palco.dataset.centrado === "1") return;
    var atual = palco.querySelector(".estado-atual");
    if (!atual) return;
    palco.dataset.centrado = "1";
    palco.scrollLeft = atual.offsetLeft + atual.offsetWidth / 2 - palco.clientWidth / 2;
    palco.scrollTop = atual.offsetTop + atual.offsetHeight / 2 - palco.clientHeight / 2;
    px = palco.scrollLeft;
    agendar();
  }

  /* ---------------------------------------------------------------------
   * Contador: ao trocar de mes os valores sobem ate o novo numero em vez de
   * simplesmente aparecerem trocados. So anima quando o valor REALMENTE muda
   * - animar na primeira pintura faria tudo piscar de zero a cada redesenho.
   * ------------------------------------------------------------------- */
  var ALVOS = ".kpi-valor, .col-sobra, .fx-sobra, .fx-acum, .ano-titulo";
  /* Map por IDENTIDADE do dado, nao por elemento: o Dash destroi e recria os
   * nos a cada atualizacao, entao um WeakMap por elemento sempre veria um no
   * novo sem historico e nunca animaria. A chave e o rotulo ao lado do valor,
   * que so muda quando o indicador em si muda. */
  var anteriores = new Map();

  function chaveDe(el) {
    var cartao = el.closest(".neu-kpi, .col-ano, .fx-linha, .neu-ano");
    var rot = cartao && cartao.querySelector(".kpi-rotulo, .col-mes, .fx-mes, .ano-sub");
    return rot ? (rot.textContent || "").trim() + "|" + el.className : null;
  }

  function partes(texto) {
    // "R$ 1.234,56" -> prefixo "R$ ", numero 1234.56, negativo?
    var m = String(texto).match(/^([^\d\-]*)(-?[\d.]+,?\d*)(.*)$/);
    if (!m) return null;
    var num = parseFloat(m[2].replace(/\./g, "").replace(",", "."));
    if (!isFinite(num)) return null;
    return { antes: m[1], valor: num, depois: m[3], casas: /,/.test(m[2]) ? 2 : 0 };
  }

  function formatar(v, casas, antes, depois) {
    var s = Math.abs(v).toFixed(casas);
    var p = s.split(".");
    p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return antes + (v < 0 ? "-" : "") + p.join(",") + depois;
  }

  function contar(el, de, para, casas, antes, depois) {
    var inicio = null;
    var dur = 620;
    function passo(agora) {
      if (inicio === null) inicio = agora;
      var t = Math.min(1, (agora - inicio) / dur);
      // desacelera no fim: o numero "assenta" em vez de parar seco
      var e = 1 - Math.pow(1 - t, 3);
      el.textContent = formatar(de + (para - de) * e, casas, antes, depois);
      if (t < 1) window.requestAnimationFrame(passo);
      else el.textContent = formatar(para, casas, antes, depois);
    }
    window.requestAnimationFrame(passo);
  }

  function animarValores() {
    document.querySelectorAll(ALVOS).forEach(function (el) {
      if (el.dataset.animando === "1") return;
      var p = partes(el.textContent);
      if (!p) return;
      var chave = chaveDe(el);
      if (!chave) return;
      var anterior = anteriores.get(chave);
      anteriores.set(chave, p.valor);
      if (anterior === undefined || anterior === p.valor) return;
      el.dataset.animando = "1";
      contar(el, anterior, p.valor, p.casas, p.antes, p.depois);
      window.setTimeout(function () { delete el.dataset.animando; }, 700);
    });
    // O mapa some da tela ao trocar de pagina; sem esta poda o Map cresceria
    // para sempre guardando indicadores que nao existem mais.
    if (anteriores.size > 400) anteriores.clear();
  }

  /* ---------------------------------------------------------------------
   * Texto sendo escrito: ao trocar de mes os titulos se reescrevem letra a
   * letra. Mesma regra do contador - so anima quando o texto muda, senao
   * todo redesenho faria a tela inteira "tremer".
   * ------------------------------------------------------------------- */
  var TEXTOS = ".exec-titulo, .mapa-hero h2, .pop-resumo";
  var textosAnteriores = new WeakMap();

  function digitar(el, texto) {
    var i = 0;
    el.classList.add("digitando");
    el.textContent = "";
    // ~18ms por letra: rapido o bastante para nao irritar, lento o bastante
    // para o olho perceber que foi reescrito.
    var timer = window.setInterval(function () {
      i += 1;
      el.textContent = texto.slice(0, i);
      if (i >= texto.length) {
        window.clearInterval(timer);
        el.classList.remove("digitando");
        delete el.dataset.digitando;
      }
    }, 18);
  }

  function animarTextos() {
    document.querySelectorAll(TEXTOS).forEach(function (el) {
      if (el.dataset.digitando === "1") return;
      var atual = (el.textContent || "").trim();
      if (!atual || atual.length > 140) return;
      var anterior = textosAnteriores.get(el);
      textosAnteriores.set(el, atual);
      if (anterior === undefined || anterior === atual) return;
      el.dataset.digitando = "1";
      digitar(el, atual);
    });
  }

  /* A barra lateral nao tem classe propria (so utilitarios do Bootstrap).
   * Marcamos ela uma vez para o CSS e o botao de ocultar conseguirem mira-la. */
  function marcarSidebar() {
    if (document.querySelector(".sidebar")) return;
    var link = document.querySelector(".nav-link");
    if (!link) return;
    var caixa = link.closest("div[style]");
    if (caixa && /position:\s*fixed/.test(caixa.getAttribute("style") || "")) {
      caixa.classList.add("sidebar");
    }
  }

  /* Ocultar o menu no desktop. Fica em classe no <body> e nao em callback do
   * Dash: assim a barra nao e reconstruida, ela apenas desliza. */
  function ligarBotaoMenu() {
    var btn = document.querySelector("#btn-ocultar-sidebar");
    if (!btn || btn.dataset.ligado === "1") return;
    btn.dataset.ligado = "1";
    if (window.localStorage.getItem("menu-oculto") === "1") {
      document.body.classList.add("menu-oculto");
    }
    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      var oculto = document.body.classList.toggle("menu-oculto");
      window.localStorage.setItem("menu-oculto", oculto ? "1" : "0");
    });
  }

  function manter() {
    garantirFundo();
    marcarSidebar();
    centralizar();
    animarValores();
    animarTextos();
    ligarBotaoMenu();
  }

  new MutationObserver(manter).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  document.addEventListener("DOMContentLoaded", manter);
  manter();
})();
