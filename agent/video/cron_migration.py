"""Payload migration for the existing Hermes TikTok job, without rescheduling."""
PROMPT = '''Voce coordena a producao afiliada TikTok nos horarios ja autorizados.
Leia /root/tools/tiktok/AGENTS.md, AUTONOMIA.md, AUTONOMIA-MAPA.md e VIDEO-QUALITY.md.
Execute python3 /root/tools/tiktok/affiliate_autonomy.py tick.
Se existing_campaign ou resume_registry, consulte o cartao/etapa e retome somente
a pendencia usando os checkpoints. Nao criar campanha concorrente, refazer acao
ambigua nem repetir produto. Se dispatched, acompanhar os cartoes nativos; isso
nao comprova video pronto ou publicado. Se catalog_exhausted, seguir o aviso
deduplicado e pesquisar sugestoes sem inventar link afiliado.
Nunca usar publicador legado como fallback. Falha de login, credito ou revisao
mantem etapa pendente com motivo factual, sem contornar controles.
Montagem exige media-preflight.json ligado ao hash do MP4, ASR e inspecao visual.
Roteiro e cenas seguem fatos atuais e a linguagem natural dos perfis existentes.
Entrega final completa com prefixo do agente real, paragrafos curtos e URL exata
somente depois de reler post e comentario. Gerar, revisar e publicar sao estados
distintos. Reutilize os recibos; nao execute postagem para validar uma resposta.
'''


def updates_for(job):
    if job.get('name') != 'tiktok-mercenario-5x' or job.get('fire_claim'):
        raise ValueError('Wrong job or active execution claim; do not modify')
    prompt = job.get('prompt', '')
    if prompt != PROMPT and 'auto_tiktok_publicador_loop.py' not in prompt:
        raise ValueError('Unexpected current prompt; inspect before migrating')
    # Old execution text may contain legacy instructions. Keep its audit history,
    # but stop replaying it as context for the new guarded entrypoint.
    return {'prompt': PROMPT, 'context_from': []}
