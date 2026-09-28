"""Visual goals and a recorded decision tree, installed on the existing Dash app."""
import base64,datetime,io,json,math,pathlib,re,sqlite3,uuid
from contextlib import contextmanager
from urllib.parse import urlencode
from finance_scenarios import scenarios
from finance_motion import spatial_outputs

def brl(value,decimals=2):
 return format(float(value),f',.{decimals}f').replace(',', '_').replace('.', ',').replace('_', '.')

def install(app,db_path,is_authed):
 from dash import html,dcc,Input,Output,State,dash_table
 import dash_bootstrap_components as dbc
 import plotly.graph_objects as go
 import flask
 from PIL import Image
 root=pathlib.Path(db_path).resolve().parent/'finance-private-media';root.mkdir(exist_ok=True,mode=0o700)
 @contextmanager
 def connection():
  con=sqlite3.connect(db_path,timeout=10);con.row_factory=sqlite3.Row
  try:
   with con:yield con
  finally:con.close()
 with connection() as con:
  con.executescript('''CREATE TABLE IF NOT EXISTS goal_visuals(meta_id INTEGER PRIMARY KEY,kind TEXT,region TEXT,latitude REAL,longitude REAL,image TEXT,motivation TEXT);
  CREATE TABLE IF NOT EXISTS decision_runs(id TEXT PRIMARY KEY,created TEXT,meta_id INTEGER,chosen TEXT,reason TEXT,inputs TEXT,alternatives TEXT);''')
 def goals():
  with connection() as con:return [dict(r) for r in con.execute('SELECT m.*,v.kind,v.region,v.latitude,v.longitude,v.image,v.motivation FROM metas m LEFT JOIN goal_visuals v ON v.meta_id=m.id ORDER BY m.id')]
 def save_image(contents):
  if not contents:return None
  if len(contents)>4200000:raise ValueError('Imagem excede 3 MB')
  prefix,raw=contents.split(',',1)
  if prefix not in ('data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'):raise ValueError('Use JPEG, PNG ou WebP')
  data=base64.b64decode(raw,validate=True)
  with Image.open(io.BytesIO(data)) as im:
   if im.width*im.height>25000000:raise ValueError('Imagem muito grande')
   im=im.convert('RGB');im.thumbnail((1400,1000));key=uuid.uuid4().hex+'.jpg';im.save(root/key,quality=86)
  return key
 @app.server.route('/goal-image/<name>')
 def goal_image(name):
  if not is_authed():return flask.abort(401)
  if not re.fullmatch(r'[a-f0-9]{32}\.jpg',name):return flask.abort(404)
  response=flask.send_from_directory(root,name);response.headers['Cache-Control']='private, no-store';return response
 def field(label,id,value=0):return html.Div([html.Label(label),dbc.Input(id=id,type='number',min=0,value=value)],className='plan-field')
 def page():
  rows=goals();options=[{'label':r['nome'],'value':r['id']} for r in rows]
  return dbc.Container([
   html.Div([html.Div('PLANEJAMENTO PESSOAL',className='plan-eyebrow'),html.H2('Uma meta. Caminhos possíveis.'),html.P('Compare tempo, esforço e dinheiro. Registre sua escolha e acompanhe o caminho.',className='text-muted')],className='plan-hero'),
   dbc.Row([
    dbc.Col(dbc.Card(dbc.CardBody([
     html.H5('Premissas do cenário'),html.Label('Meta existente'),dcc.Dropdown(id='plan-goal',options=options,value=rows[0]['id'] if rows else None),
     field('Valor da meta (R$)','plan-target',rows[0]['valor_alvo'] if rows else 0),field('Já reservado (R$)','plan-current',rows[0]['valor_atual'] if rows else 0),
     field('Aporte mensal disponível (R$)','plan-monthly'),field('Redução mensal de despesas (R$)','plan-reduction'),field('Horas extras por mês','plan-hours'),field('Valor líquido por hora (R$)','plan-rate'),
     html.P('As projeções dependem dos valores informados. Não incluem rendimento, inflação ou garantia de renda.',className='plan-note'),
    ])),md=4,className='mb-4'),
    dbc.Col([dcc.Graph(id='plan-tree',config={'displayModeBar':False}),html.Div(id='plan-table'),dcc.Store(id='plan-inputs'),dcc.Store(id='plan-paths')],md=8),
   ]),
   dbc.Card(dbc.CardBody([html.H5('Decisão tomada'),dcc.Dropdown(id='plan-choice',options=[{'label':v,'value':k} for k,v in [('current','Manter o plano'),('reduce','Reduzir despesas'),('hours','Adicionar horas'),('combined','Combinar ajustes')]],value='current'),dbc.Textarea(id='plan-reason',placeholder='Por que você escolheu esse caminho? Quais condições precisam se manter?'),dbc.Button('Registrar escolha',id='plan-save',className='mt-3'),html.Div(id='plan-save-result'),html.Div(id='plan-history',className='mt-3')]),className='mb-4'),
   html.Div([html.H3('Metas que você consegue visualizar'),html.P('Adicione sua imagem, intenção e localização. O mapa usa coordenadas informadas por você.',className='text-muted')]),
   dbc.Row([dbc.Col(dbc.Card(dbc.CardBody([
    html.Label('Meta'),dcc.Dropdown(id='visual-goal',options=options,value=rows[0]['id'] if rows else None),
    html.Label('Tipo'),dcc.Dropdown(id='visual-kind',options=[{'label':x,'value':x} for x in ('Objeto','Viagem','Moradia','Experiência','Reserva')],value='Objeto'),
    dbc.Input(id='visual-region',placeholder='Cidade / região (opcional)',className='mt-3'),
    dbc.Input(id='visual-lat',type='number',min=-90,max=90,placeholder='Latitude',className='mt-2'),dbc.Input(id='visual-lon',type='number',min=-180,max=180,placeholder='Longitude',className='mt-2'),
    dbc.Textarea(id='visual-motivation',placeholder='Como essa conquista muda sua vida?',className='mt-3'),
    dcc.Upload(id='visual-upload',children=html.Div('Selecionar imagem · JPEG / PNG / WebP · até 3 MB'),multiple=False,className='plan-upload'),
    dbc.Button('Salvar visão da meta',id='visual-save'),html.Div(id='visual-result')
   ])),md=4),dbc.Col(html.Div(id='visual-gallery'),md=8)]),
  ],fluid=True,className='planning-page')
 @app.callback(Output('plan-target','value'),Output('plan-current','value'),Input('plan-goal','value'))
 def select_goal(mid):
  if not is_authed():return 0,0
  row=next((x for x in goals() if x['id']==mid),None)
  return (row['valor_alvo'],row['valor_atual']) if row else (0,0)
 @app.callback(Output('plan-tree','figure'),Output('plan-table','children'),Output('plan-inputs','data'),Output('plan-paths','data'),
  Input('plan-target','value'),Input('plan-current','value'),Input('plan-monthly','value'),Input('plan-reduction','value'),Input('plan-hours','value'),Input('plan-rate','value'),Input('plan-choice','value'))
 @spatial_outputs(["plan-tree",None,None,None])
 def calculate(target,current,monthly,reduction,hours,rate,chosen):
  fig=go.Figure();inputs=dict(target=target,current=current,monthly=monthly,expense_reduction=reduction,extra_hours=hours,hour_rate=rate)
  if not is_authed():return fig,'',{},[]
  try:paths=scenarios(**inputs)
  except (ValueError,TypeError):return fig,dbc.Alert('Revise as premissas numéricas.',color='warning'),{},[]
  for i,path in enumerate(paths):
   x=(i-1.5)*2;selected=path['id']==chosen;color='#cdb0dc' if selected else '#6c91ac';months='Sem prazo calculável' if path['months'] is None else str(path['months'])+' meses'
   fig.add_trace(go.Scatter3d(x=[0,x,x],y=[0,0,0],z=[3,2,.5],mode='lines',line={'color':color,'width':4 if selected else 1.5},hoverinfo='skip',showlegend=False))
   fig.add_trace(go.Scatter3d(x=[x,x],y=[0,0],z=[2,.5],mode='markers+text',text=[path['label'],f"R$ {brl(path['monthly'],0)}/mês<br>{months}"],textposition='top center',marker={'size':7,'color':color},textfont={'color':'#314c61','size':11},showlegend=False,hoverinfo='text'))
  fig.add_annotation(x=.5,y=.99,xref='paper',yref='paper',text='SITUAÇÃO ATUAL<br>Falta R$ '+f"{brl(paths[0]['gap'],0)}",showarrow=False,bgcolor='#364152',borderpad=15,font={'color':'#eae9f4'})
  fig.update_layout(title='Árvore de cenários · ramo destacado = escolha em edição',height=450,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font={'color':'#b8bed0'},margin={'l':20,'r':20,'t':55,'b':15},xaxis={'visible':False,'range':[-4.4,4.4]},yaxis={'visible':False,'range':[0,3.5]})
  fig.update_layout(scene={'xaxis':{'visible':False},'yaxis':{'visible':False},'zaxis':{'visible':False},'aspectmode':'manual','aspectratio':{'x':2,'y':.3,'z':1},'camera':{'eye':{'x':.15,'y':-2.3,'z':.5},'projection':{'type':'orthographic'}}})
  table=dbc.Table([html.Thead(html.Tr([html.Th(x) for x in ('Caminho','Aporte mensal','Horas extras','Prazo simulado')])),html.Tbody([html.Tr([html.Td(p['label']),html.Td(f"R$ {brl(p['monthly'])}"),html.Td(p['extra_hours']),html.Td(str(p['months'])+' meses' if p['months'] is not None else 'Indefinido')]) for p in paths])],responsive=True,borderless=True,hover=True)
  return fig,table,inputs,paths
 @app.callback(Output('plan-save-result','children'),Output('plan-history','children'),Input('plan-save','n_clicks'),State('plan-goal','value'),State('plan-choice','value'),State('plan-reason','value'),State('plan-inputs','data'))
 def save_decision(click,mid,chosen,reason,inputs):
  if not is_authed():return '',[]
  notice=''
  if click:
   try:
    paths=scenarios(**(inputs or {}))
    if chosen not in {p['id'] for p in paths} or not reason or len(reason)>2000:raise ValueError('Informe o motivo da escolha, até 2000 caracteres')
    with connection() as con:con.execute('INSERT INTO decision_runs VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,datetime.datetime.now(datetime.timezone.utc).isoformat(),mid,chosen,reason,json.dumps(inputs),json.dumps(paths)))
    notice='Escolha e alternativas registradas. Isso não altera saldos nem executa operações.'
   except (ValueError,TypeError) as exc:notice=str(exc)
  with connection() as con:history=[dict(r) for r in con.execute('SELECT * FROM decision_runs ORDER BY created DESC LIMIT 10')]
  return notice,[html.Details([html.Summary(r['created'][:16].replace('T',' ')+' · '+r['chosen']),html.P(r['reason']),html.Pre(json.dumps(json.loads(r['alternatives']),ensure_ascii=False,indent=2))]) for r in history]
 @app.callback(Output('visual-result','children'),Output('visual-gallery','children'),Input('visual-save','n_clicks'),State('visual-goal','value'),State('visual-kind','value'),State('visual-region','value'),State('visual-lat','value'),State('visual-lon','value'),State('visual-motivation','value'),State('visual-upload','contents'))
 def save_visual(click,mid,kind,region,lat,lon,motivation,contents):
  if not is_authed():return '',[]
  notice=''
  if click:
   try:
    if mid not in {g['id'] for g in goals()}:raise ValueError('Escolha uma meta existente')
    if (lat is None)!=(lon is None):raise ValueError('Informe latitude e longitude juntas')
    if lat is not None and (not math.isfinite(float(lat)) or not math.isfinite(float(lon)) or not -90<=float(lat)<=90 or not -180<=float(lon)<=180):raise ValueError('Coordenadas inválidas')
    if len(region or '')>160 or len(motivation or '')>2000:raise ValueError('Texto excede limite')
    image=save_image(contents)
    with connection() as con:
     old=con.execute('SELECT image FROM goal_visuals WHERE meta_id=?',(mid,)).fetchone()
     con.execute('INSERT OR REPLACE INTO goal_visuals VALUES(?,?,?,?,?,?,?)',(mid,kind,region or '',lat,lon,image or (old['image'] if old else None),motivation or ''))
    notice='Visão salva.'
   except (ValueError,TypeError,Image.DecompressionBombError) as exc:notice=str(exc)
  cards=[]
  for goal in goals():
   parts=[html.H4(goal['nome']),html.P(goal.get('motivation') or 'Defina o significado desta meta.'),html.P(goal.get('region') or goal.get('kind') or 'Meta pessoal',className='text-muted')]
   if goal.get('image'):parts.insert(0,html.Img(src='/goal-image/'+goal['image'],className='goal-photo'))
   if goal.get('latitude') is not None:
    lat,lon=goal['latitude'],goal['longitude'];url='https://www.openstreetmap.org/export/embed.html?'+urlencode({'bbox':f'{lon-.06},{lat-.04},{lon+.06},{lat+.04}','layer':'mapnik','marker':f'{lat},{lon}'})
    parts.append(html.Iframe(src=url,title='Mapa da região da meta',className='goal-map',referrerPolicy='no-referrer'))
   parts.append(html.P(f"R$ {brl(goal['valor_atual'])} / R$ {brl(goal['valor_alvo'])}"))
   cards.append(dbc.Card(dbc.CardBody(parts),className='goal-vision mb-4'))
  return notice,cards
 return page
