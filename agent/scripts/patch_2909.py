"""Patches idempotentes do runtime/report do meeting_copilot e do worker do ultron_team (preserva CRLF)."""
import sys
from pathlib import Path


def eol_of(text, anchor):
    i = text.index(anchor)
    j = text.index('\n', i)
    return '\r\n' if text[j - 1] == '\r' else '\n'


def patch_runtime(path):
    p = Path(path); s = p.read_bytes().decode('utf-8'); changed = False
    if 'async def _diarizar' not in s:
        a = "        payload = {'session':self.store.get(sid),'report_text':final,"
        eol = eol_of(s, a)
        s = s.replace(a, '        diar = await self._diarizar(sid)' + eol + a, 1)
        old = "'pending_findings':[row['finding'] for row in pending],'ended_at':time.time()}"
        assert s.count(old) == 1, 'payload'
        s = s.replace(old, "'pending_findings':[row['finding'] for row in pending],'ended_at':time.time(),'speakers':diar,"
                      "'transcript_events':[{'id':e['id'],'at':e['at'],'end':(e.get('extra') or {}).get('end'),'channel':e['channel'],"
                      "'text':e['text'],'confidence':(e.get('extra') or {}).get('confidence')} for e in self.store.events(sid) "
                      "if e['kind']=='transcript' and e['text'].strip()]}")
        m = '    async def email(self, sid):'
        eol = eol_of(s, m)
        metodo = '''    async def _diarizar(self, sid):
        """Separa as vozes do áudio recebido da reunião (local, CPU). Falha nunca impede a ata."""
        python = self.settings.get('stt_python','/root/tools/stt-venv/bin/python')
        script = self.settings.get('diarize_script','/root/tools/stt/diarizar.py')
        root = Path(self.settings.get('capture_audio_root','/mnt/c/Users/yurim/tools/copilot/capture_state'))
        if not Path(python).exists() or not Path(script).exists():
            return {}
        events = [{'id':e['id'],'at':e['at'],'end':(e.get('extra') or {}).get('end'),'channel':e['channel']}
                  for e in self.store.events(sid) if e['kind']=='transcript']
        request = json.dumps({'audio_dir':str(root/sid/'audio'),'events':events}).encode()
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(python, script, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, _ = await asyncio.wait_for(proc.communicate(request), timeout=600)
            return json.loads(out.decode().strip().splitlines()[-1])
        except Exception:
            if proc and proc.returncode is None:
                proc.kill()
            return {}

'''.replace('\n', eol)
        s = s.replace(m, metodo + m, 1)
        changed = True
    if "render_docx.py" not in s:
        a = "        self.store.update(sid,report_pdf=str(pdf),report_transcript=str(transcript),ended=time.time())"
        eol = eol_of(s, a)
        bloco = '''        docx = directory/'ata-formal.docx'
        try:
            proc_docx = await asyncio.create_subprocess_exec(self.settings.get('tools_python','/root/tools/venv/bin/python'),
                  str(Path(__file__).with_name('render_docx.py')),str(source),str(docx),
                  stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            await asyncio.wait_for(proc_docx.communicate(),timeout=120)
        except Exception:
            pass
'''.replace('\n', eol)
        s = s.replace(a, bloco + a, 1)
        t = "await self.delivery.document(self.store.get(sid),pdf,'Transcrição e análise da reunião')"
        eol = eol_of(s, t)
        linha = next(l for l in s.split(eol) if t in l)
        ind = linha[:len(linha) - len(linha.lstrip())]
        s = s.replace(linha, linha + eol + ind + "if docx.is_file():" + eol + ind +
                      "    await self.delivery.document(self.store.get(sid),docx,'Ata formal editável (Word)')", 1)
        changed = True
    if changed:
        p.write_bytes(s.encode('utf-8'))
    print('runtime', 'atualizado' if changed else 'já estava')


def patch_report(path):
    p = Path(path); s = p.read_text(encoding='utf-8')
    if 'ata-formal.docx' in s:
        print('report já estava'); return
    old = "f'Relatório executivo da reunião em anexo.\\nSessão: {session_id}\\n', [pdf_path])"
    assert s.count(old) == 1, 'report'
    s = s.replace(old, "f'Ata formal (PDF e Word editável) e relatório executivo em anexo.\\nSessão: {session_id}\\n', "
                       "[pdf_path] + [x for x in [Path(pdf_path).with_name('ata-formal.docx')] if x.is_file()])")
    p.write_text(s, encoding='utf-8'); print('report atualizado')


def patch_worker(path):
    p = Path(path); s = p.read_text(encoding='utf-8')
    if 'ultron_agentes' in s:
        print('worker já estava'); return
    old = "    else:\n        # Conselheiro: analisa e vota com o que sabe. Nao opera nada.\n"
    assert s.count(old) == 1, 'worker'
    new = ("    elif profile in ('bigode', 'buffett', 'tron', 'mrrobot'):\n"
           "        # Dados reais somente leitura: BCB/BrasilAPI/B3 (financas) ou auditoria/backup (seguranca).\n"
           "        from ultron_agentes import register_agent_tools\n"
           "        agent_toolset, agent_prompt = register_agent_tools(registry.register, profile, home, base)\n"
           "        toolsets = [agent_toolset, 'memory', 'kanban', 'hermes_rag']\n"
           "        extra_prompt = agent_prompt + ' '\n" + old)
    s = s.replace(old, new); p.write_text(s, encoding='utf-8'); print('worker atualizado')


if __name__ == '__main__':
    alvo, path = sys.argv[1], sys.argv[2]
    {'runtime': patch_runtime, 'report': patch_report, 'worker': patch_worker}[alvo](path)
