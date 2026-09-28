"""Deterministic planning scenarios. No price forecasts or trading execution."""
import math

def scenarios(target,current,monthly,expense_reduction,extra_hours,hour_rate):
 values=[float(x or 0) for x in (target,current,monthly,expense_reduction,extra_hours,hour_rate)]
 if not all(math.isfinite(x) and x>=0 for x in values):raise ValueError('Use valores finitos, iguais ou maiores que zero')
 target,current,monthly,reduction,hours,rate=values
 gap=max(0,target-current)
 options=[('current','Manter o plano',monthly,0),('reduce','Reduzir despesas',monthly+reduction,0),
          ('hours','Adicionar horas',monthly+hours*rate,hours),('combined','Combinar ajustes',monthly+reduction+hours*rate,hours)]
 return [{'id':key,'label':label,'monthly':round(amount,2),'extra_hours':effort,
          'months':0 if gap==0 else math.ceil(gap/amount) if amount>0 else None,
          'gap':round(gap,2),'assumptions':'Sem rendimento financeiro; preços constantes; horas extras precisam ser recebidas.'}
         for key,label,amount,effort in options]
