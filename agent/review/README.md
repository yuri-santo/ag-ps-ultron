# Triagem e revisão do Ultron

`ultron_review_gate.py` faz triagem apenas de saudações sociais isoladas. Pedidos
mistos, técnicos, médicos, financeiros ou com ações continuam na revisão do
`model_review.py`. O broker mantém tickets privados em `reviews/queue/`, atende
conversas antes de jobs agendados e conserva a ordem de chegada dentro de cada
classe. Tickets de processos mortos não bloqueiam a fila.

O patch reproduzível `patch_review_stop_gate.py` liga o parecer de correção ao
ciclo de resposta do Hermes. A primeira versão reprovada não é emitida ao
usuário; há uma tentativa de revisão no mesmo turno. O parecer cru fica só no
registro privado. O patch recusa um arquivo upstream com âncora diferente e
salva backup antes de modificar `turn_stop_gates.py`.

```sh
sudo cp agent/review/model_review.py /root/ultron-local/model_review.py
sudo cp agent/review/ultron_review_gate.py /opt/hermes-agent-20260924/agent/ultron_review_gate.py
sudo python3 agent/review/patch_review_stop_gate.py /opt/hermes-agent-20260924/agent/turn_stop_gates.py
python3 -m unittest discover -s agent/review -p 'test_*.py' -v
```

Faça backup dos dois arquivos vivos antes de copiá-los. O agendador fornece
`_ultron_cron_task` e `_ultron_cron_evidence` para que o revisor avalie a tarefa
real, não instruções de uma skill carregada. Reinicie o gateway depois de
verificar sintaxe e testes.

Esta fila coordena **revisões**, não transforma toda tarefa longa em job
durável. Se o serviço de revisão falhar ou estourar o limite, a entrega segue
bloqueada com aviso genérico em PT-BR, sem aprovação presumida. A entrega
assíncrona completa em outra mensagem exige uma fila de tarefas e um canal de
retorno persistentes; não é alegada por este módulo.
