---
name: memoria-projetos
description: Usa o ai-memory para lembrar projetos e passar o bastão
version: 1.0.0
metadata:
  hermes:
    category: ultron-lab
    tags: [memoria, ai-memory, handoff, mcp, projetos]
---

# Memória de projetos com ai-memory

O ai-memory (akitaonrails/ai-memory) roda no stack `ia` do homelab (porta 49374) e guarda uma wiki em
markdown versionada em git por projeto. O mesmo servidor atende Claude Code, Codex, Cursor e outros:
o que um agente aprende, os outros recuperam. Esta skill só vale depois que o servidor MCP `ai_memory`
estiver no `config.yaml` do Hermes:

```yaml
mcp_servers:
  ai_memory:
    url: "http://127.0.0.1:49374/mcp"
    headers:
      Authorization: "Bearer <AI_MEMORY_AUTH_TOKEN>"
    tools:
      include: [memory_briefing, memory_query, memory_read_page, memory_recent, memory_status,
                memory_handoff_list, memory_handoff_accept, memory_handoff_begin, memory_write_page]
```

## Quando usar

- Yuri volta a um projeto ("onde parei no Trader Firme?", "o que decidimos sobre o cutover?").
- Yuri vai trocar de ferramenta (do Ultron para o Claude Code/Codex no PC) e quer passar o contexto.
- Uma decisão, pegadinha ou procedimento durável apareceu e vale guardar.

## Passos

1. **Recuperar:** `memory_briefing` do projeto; se não bastar, `memory_query` com termos concretos
   (nomes de arquivo, erro, cliente). Leia a página com `memory_read_page` antes de citar.
2. **Responder citando a página** (título/caminho). Se a memória não tiver, diga que não tem.
3. **Guardar:** só fato durável (decisão, motivo, comando que funcionou, armadilha). Nada de segredo,
   senha, token, dado de cliente sensível ou conversa pessoal. Confirme com Yuri antes de `memory_write_page`.
4. **Passar o bastão:** `memory_handoff_begin` com onde parou, o que falhou e o que falta; no outro agente,
   `memory_handoff_accept`. O Hermes ignora a saída do hook de início de sessão, então o aceite é sempre
   explícito via MCP.

## Regras

- Memória é pista, não verdade: confira no código/arquivo antes de afirmar que algo "está assim".
- Não use o ai-memory para e-mail, finanças pessoais ou dados de terceiros; o escopo é projeto.
- Sem ferramenta `memory_*` disponível: diga que o MCP do ai-memory não está configurado.
