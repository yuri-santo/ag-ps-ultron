"""Interactive 3D presentation of existing financial figures; no database access."""
from copy import deepcopy
from functools import wraps
import base64
import hashlib
import math
from html import escape

import numpy as np
import plotly.graph_objects as go
from dash import dcc

COLORS=['#55adca','#897fce','#5eaf96','#d59db2','#caa768','#738db9','#85b8c1']

def sequence(value):
    if value is None:return []
    if isinstance(value,dict) and 'bdata' in value:
        a=np.frombuffer(base64.b64decode(value['bdata']),dtype=value['dtype'])
        if value.get('shape'):a=a.reshape(tuple(int(x) for x in str(value['shape']).split(',')))
        return a.tolist()
    if hasattr(value,'tolist'):return value.tolist()
    return list(value)

def number(value):
    if value is None:return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (TypeError,ValueError):return None

def color(trace,index):
    marker=trace.get('marker') or {};line=trace.get('line') or {}
    value=marker.get('color') or line.get('color') if not isinstance(marker.get('color'),np.ndarray) else None
    return value if isinstance(value,str) else COLORS[index%len(COLORS)]

def money_text(value):
    return f'{value:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def uid(key,name):return hashlib.sha256((str(key)+'|'+str(name)).encode()).hexdigest()[:20]

TRIANGLES=[(0,1,2),(0,2,3),(4,6,5),(4,7,6),(0,4,5),(0,5,1),
           (1,5,6),(1,6,2),(2,6,7),(2,7,3),(3,7,4),(3,4,0)]

def bars(trace,labels,lane,key,bases=None,values=None,positions=None):
    values=values if values is not None else [number(v) for v in sequence(trace.get('y'))]
    name=str(trace.get('name') or 'Valores')
    xs=[];ys=[];zs=[];ii=[];jj=[];kk=[];custom=[];ids=[];vertex_colors=[]
    source_colors=trace.get('marker',{}).get('color')
    source_colors=sequence(source_colors) if not isinstance(source_colors,str) and source_colors is not None else []
    for pos,value in enumerate(values):
        if value is None:continue
        base=(bases or [0]*len(values))[pos];end=base+value
        low,high=min(base,end),max(base,end)
        center=positions[pos] if positions is not None else pos
        x0,x1=center-.34,center+.34;y0,y1=lane-.25,lane+.25
        offset=len(xs)
        xs.extend([x0,x1,x1,x0,x0,x1,x1,x0]);ys.extend([y0,y0,y1,y1,y0,y0,y1,y1])
        zs.extend([low]*4+[high]*4)
        label=str(labels[pos]) if pos<len(labels) else str(pos)
        for vertex in range(8):
            custom.append([escape(label),value,escape(name)])
            ids.append(label+':'+str(vertex))
            c=source_colors[pos] if pos<len(source_colors) and isinstance(source_colors[pos],str) else color(trace,lane)
            vertex_colors.append(c)
        for a,b,c in TRIANGLES:ii.append(offset+a);jj.append(offset+b);kk.append(offset+c)
    return go.Mesh3d(x=xs,y=ys,z=zs,i=ii,j=jj,k=kk,customdata=custom,ids=ids,showlegend=True,
        vertexcolor=vertex_colors,name=name,uid=uid(key,name),flatshading=True,
        lighting=dict(ambient=.68,diffuse=.85,roughness=.48,specular=.18),
        lightposition=dict(x=-120,y=-80,z=180),showscale=False,
        hovertemplate='%{customdata[0]}<br>%{customdata[2]}: %{customdata[1]:,.2f}<extra></extra>')

def ring_sector(start,end,inner,value,label,key,index,total):
    steps=32  # Stable topology lets every distribution morph between months.
    angles=np.linspace(start,end,steps+1).tolist()
    xs=[];ys=[];zs=[];ii=[];jj=[];kk=[]
    for a in angles:
        for radius,z in ((inner,0),(1,0),(inner,.16),(1,.16)):
            xs.append(radius*math.cos(a));ys.append(radius*math.sin(a));zs.append(z)
    for n in range(steps):
        p=n*4;q=(n+1)*4
        for a,b,c in ((p+2,p+3,q+3),(p+2,q+3,q+2),(p,p+1,q+1),(p,q+1,q),
                      (p+1,p+3,q+3),(p+1,q+3,q+1),(p,p+2,q+2),(p,q+2,q)):
            ii.append(a);jj.append(b);kk.append(c)
    for p in (0,steps*4):
        for a,b,c in ((p,p+1,p+3),(p,p+3,p+2)):ii.append(a);jj.append(b);kk.append(c)
    share=value/total if total else 0
    return go.Mesh3d(x=xs,y=ys,z=zs,i=ii,j=jj,k=kk,color=COLORS[index%len(COLORS)],
        name=str(label),uid=uid(key,str(label)),ids=[str(n) for n in range(len(xs))],
        customdata=[[escape(str(label)),value,share] for _ in xs],meta={'share':share},
        flatshading=False,lighting=dict(ambient=.75,diffuse=.8,roughness=.5),
        lightposition=dict(x=-80,y=-80,z=140),showlegend=True,
        hovertemplate='%{customdata[0]}<br>%{customdata[1]:,.2f} · %{customdata[2]:.1%}<extra></extra>')

def spatial_figure(figure,key,period=None):
    source=deepcopy(figure.to_plotly_json() if hasattr(figure,'to_plotly_json') else (figure or {}))
    old_layout=source.get('layout') or {}
    old_meta=old_layout.get('meta') or {}
    if isinstance(old_meta,dict) and old_meta.get('motion',{}).get('spatial'):
        result=go.Figure(source);result.layout.meta['motion'].update(key=key,period=period)
        return result
    traces=source.get('data') or [];result=go.Figure();all_values=[]
    if traces and all(t.get('type') in ('scatter3d','mesh3d','surface') for t in traces):
        result=go.Figure(source)
        result.update_layout(uirevision=key,scene_uirevision=key,meta={'motion':{'key':key,'period':period,'spatial':True,'source_types':['native3d'],'values':[],'version':1}})
        return result
    xlabels=[];ynames=[];round_chart=False;kind=[];stack_positive={};stack_negative={}
    all_x=[]
    for trace in traces:
        if trace.get('type') in ('bar','scatter','scattergl','waterfall'):
            for v in sequence(trace.get('y' if trace.get('orientation')=='h' else 'x')):
                text=str(v)
                if text not in all_x:all_x.append(text)
    for lane,trace in enumerate(traces):
        kind.append(trace.get('type','scatter'));name=str(trace.get('name') or f'Série {lane+1}')
        typ=trace.get('type','scatter')
        if typ in ('bar','waterfall'):
            horizontal=trace.get('orientation')=='h'
            labels=[str(v) for v in sequence(trace.get('y' if horizontal else 'x'))]
            values=[number(v) for v in sequence(trace.get('x' if horizontal else 'y'))]
            if not labels:labels=[str(i+1) for i in range(len(values))]
            bases=[0.0]*len(values)
            plot_lane=lane
            if typ=='waterfall':
                running=0.;measures=sequence(trace.get('measure'))
                for i,v in enumerate(values):
                    measure=measures[i] if i<len(measures) else 'relative';v=v or 0
                    if measure=='total':values[i]=running;bases[i]=0
                    elif measure=='absolute':running=v;bases[i]=0
                    else:bases[i]=running;running+=v
            elif old_layout.get('barmode') in ('stack','relative'):
                plot_lane=0
                for i,v in enumerate(values):
                    store=stack_negative if (v or 0)<0 else stack_positive
                    bases[i]=store.get(labels[i],0.);store[labels[i]]=bases[i]+(v or 0)
            if typ=='waterfall':
                colors=[]
                for i,v in enumerate(values):
                    which='totals' if i<len(measures) and measures[i] in ('total','absolute') else ('decreasing' if (v or 0)<0 else 'increasing')
                    colors.append(trace.get(which,{}).get('marker',{}).get('color',COLORS[lane%len(COLORS)]))
                trace={**trace,'marker':{'color':colors}}
            positions=[all_x.index(v) if v in all_x else i for i,v in enumerate(labels)]
            result.add_trace(bars({**trace,'name':name},labels,plot_lane,key,bases,values,positions))
            xlabels=all_x or labels;ynames.append(name);all_values.extend(values)
        elif typ in ('scatter','scattergl','scatter3d'):
            labels=[str(v) for v in sequence(trace.get('x'))]
            values=[number(v) for v in sequence(trace.get('z' if typ=='scatter3d' else 'y'))]
            positions=[all_x.index(v) if v in all_x else i for i,v in enumerate(labels)]
            if trace.get('fill')=='tonexty' and lane and len(sequence(traces[lane-1].get('y')))==len(values):
                upper=[number(v) for v in sequence(traces[lane-1].get('y'))]
                result.add_trace(go.Surface(x=positions,y=[lane-.3,lane+.3],z=[values,upper],
                    opacity=.22,showscale=False,colorscale=[[0,'#80b9cf'],[1,'#80b9cf']],
                    name=name,uid=uid(key,name+'-interval'),hoverinfo='skip',showlegend=False))
            result.add_trace(go.Scatter3d(x=positions,y=[lane]*len(values),z=values,
                mode=trace.get('mode','lines+markers'),name=name,uid=uid(key,name),ids=labels,
                customdata=[[escape(labels[i]) if i<len(labels) else str(i),v] for i,v in enumerate(values)],
                line=dict(color=color(trace,lane),width=max(1,trace.get('line',{}).get('width',3)),dash=trace.get('line',{}).get('dash','solid')),
                marker=dict(color=color(trace,lane),size=4),text=trace.get('text'),showlegend=trace.get('showlegend',True),
                connectgaps=False,hovertemplate='%{customdata[0]}<br>%{customdata[1]:,.2f}<extra>'+escape(name)+'</extra>'))
            xlabels=all_x or labels;ynames.append(name);all_values.extend(values)
        elif typ in ('heatmap','surface'):
            matrix=sequence(trace.get('z'));matrix=[sequence(row) for row in matrix]
            labels=[str(v) for v in sequence(trace.get('x'))]
            rows=[str(v) for v in sequence(trace.get('y'))]
            if not matrix:continue
            if not labels:labels=[str(i+1) for i in range(len(matrix[0]))]
            if not rows:rows=[str(i+1) for i in range(len(matrix))]
            grid=[[number(v) for v in row] for row in matrix]
            details=[[[escape(labels[x]),escape(rows[y]),v] for x,v in enumerate(row)] for y,row in enumerate(grid)]
            if len(rows)<2 or len(labels)<2:
                for j,row in enumerate(grid):result.add_trace(bars({'name':rows[j]},labels,j,key,values=row))
            else:result.add_trace(go.Surface(x=list(range(len(labels))),y=list(range(len(rows))),z=grid,
                uid=uid(key,name),name=name,customdata=details,colorscale=[[0,'#e0f1f2'],[.45,'#77b6c9'],[1,'#8472bd']],
                colorbar=dict(thickness=10,len=.6),
                hovertemplate='%{customdata[1]} · %{customdata[0]}<br>%{z:,.2f}<extra></extra>'))
            xlabels=labels;ynames=rows;all_values.extend(v for row in grid for v in row)
        elif typ=='pie':
            values=[number(v) or 0. for v in sequence(trace.get('values'))]
            labels=sequence(trace.get('labels')) or [str(i+1) for i in range(len(values))]
            all_values.extend(values)
            if any(v<0 for v in values):
                result.add_trace(bars({'name':name},labels,0,key,values=values));xlabels=labels
            elif sum(values)>0:
                round_chart=True;angle=math.pi/2;total=sum(values)
                for i,(label,value) in enumerate(zip(labels,values)):
                    end=angle+value/total*2*math.pi
                    if value>0:
                        sector=ring_sector(angle,end,float(trace.get('hole') or .45),value,label,key,i,total)
                        original_colors=sequence(trace.get('marker',{}).get('colors'))
                        if i<len(original_colors):sector.color=original_colors[i]
                        result.add_trace(sector)
                    angle=end
                result.add_annotation(x=.5,y=.49,xref='paper',yref='paper',text=money_text(total),showarrow=False,font=dict(size=19,color='#263b51'))
        elif typ=='indicator':
            round_chart=True;value=number(trace.get('value')) or 0.;all_values.append(value)
            gauge=trace.get('gauge') or {};limits=gauge.get('axis',{}).get('range') or [0,max(value,1)]
            low=number(limits[0]) or 0.;high=number(limits[1]) or max(value,1)
            share=max(0,min(1,(value-low)/(high-low))) if high>low else 0
            if share>0:result.add_trace(ring_sector(0,share*2*math.pi,.72,share,'Atual',key,0,1))
            if share<1:
                rest=ring_sector(share*2*math.pi,2*math.pi,.72,1-share,'Restante',key,1,1)
                rest.color='#dce7ed';rest.hoverinfo='skip';result.add_trace(rest)
            number_style=trace.get('number') or {}
            label=escape(str(number_style.get('prefix','')))+money_text(value)+escape(str(number_style.get('suffix','')))
            result.add_annotation(x=.5,y=.49,xref='paper',yref='paper',text=label,showarrow=False,font=dict(size=25,color='#263b51'))
            target=number(gauge.get('threshold',{}).get('value'))
            if target is not None and high>low:
                angle=(target-low)/(high-low)*2*math.pi
                result.add_trace(go.Scatter3d(x=[.66*math.cos(angle),1.06*math.cos(angle)],y=[.66*math.sin(angle),1.06*math.sin(angle)],z=[.19,.19],
                    mode='lines',line=dict(color='#bc625a',width=6),uid=uid(key,'gauge-target'),showlegend=False,
                    meta={'reference':True,'value':target},hovertemplate=money_text(target)+'<extra>Referência</extra>'))
                result.add_annotation(x=.5,y=.12,xref='paper',yref='paper',text='Referência: '+money_text(target),showarrow=False,font=dict(size=11,color='#9b625c'))
            delta=trace.get('delta') or {}
            if number(delta.get('reference')) is not None:
                difference=value-number(delta['reference'])
                result.add_annotation(x=.5,y=.25,xref='paper',yref='paper',text='Diferença: '+money_text(difference),showarrow=False,font=dict(size=12,color='#62798b'))
        else:
            # Preserve any future unsupported graph instead of dropping financial data.
            fallback=go.Figure(source);fallback.update_layout(meta={'motion':{'key':key,'period':period,'spatial':False,'fallback':typ}})
            return fallback

    axis=dict(showbackground=True,backgroundcolor='rgba(223,236,241,.24)',gridcolor='rgba(90,115,140,.17)',
        zerolinecolor='rgba(65,90,110,.5)',tickfont=dict(size=10,color='#50697e'),showspikes=False,title='')
    ticks=list(range(0,len(xlabels),max(1,math.ceil(len(xlabels)/9))))
    scene=dict(xaxis={**axis,'tickvals':ticks,'ticktext':[str(xlabels[i])[:23]+('…' if len(str(xlabels[i]))>23 else '') for i in ticks]},
        yaxis={**axis,'tickvals':list(range(len(ynames))),'ticktext':ynames},zaxis={**axis,'title':old_layout.get('yaxis',{}).get('title') or 'Valor','rangemode':'tozero'},
        bgcolor='rgba(0,0,0,0)',aspectmode='manual',aspectratio=dict(x=3.2,y=.6,z=1),
        camera=dict(eye=dict(x=.7,y=-2,z=1.15),projection=dict(type='orthographic')),
        dragmode='orbit',uirevision=key)
    if not any(t in ('heatmap','surface') for t in kind):scene['yaxis'].update(showticklabels=False,title='')
    if round_chart:
        scene.update(xaxis=dict(visible=False),yaxis=dict(visible=False),zaxis=dict(visible=False),
            aspectratio=dict(x=1,y=1,z=.22),camera=dict(eye=dict(x=.15,y=-1.6,z=2.5),projection=dict(type='orthographic')))
    if not result.data:
        result.add_annotation(x=.5,y=.5,xref='paper',yref='paper',text='Sem dados para o período selecionado',showarrow=False,font=dict(color='#62798b',size=14))
    # Carry constant goal lines into the spatial figure, instead of losing targets.
    for i,shape in enumerate(old_layout.get('shapes') or []):
        if shape.get('type')=='line' and shape.get('yref','y')=='y' and shape.get('y0')==shape.get('y1') and number(shape.get('y0')) is not None:
            target=number(shape['y0'])
            result.add_trace(go.Scatter3d(x=[-.4,max(len(xlabels)-.6,.4)],y=[-.45,-.45],z=[target,target],mode='lines',
                line=dict(color='#bc7b66',width=3,dash='dash'),name='Referência',showlegend=False,
                uid=uid(key,'reference-'+str(i)),meta={'reference':True},hovertemplate='%{z:,.2f}<extra>Referência</extra>'))
        elif shape.get('type')=='line' and shape.get('x0')==shape.get('x1') and str(shape.get('x0')) in xlabels:
            pos=xlabels.index(str(shape['x0']));valid=[v for v in all_values if v is not None]
            result.add_trace(go.Scatter3d(x=[pos,pos],y=[-.45,-.45],z=[min(valid+[0]),max(valid+[1])],mode='lines',
                line=dict(color='#bc9766',width=4,dash='dash'),name='Mês selecionado',uid=uid(key,'selected-month'),showlegend=False,
                meta={'selected_month':str(shape['x0'])},hovertemplate=escape(str(shape['x0']))+'<extra>Mês selecionado</extra>'))
    title=old_layout.get('title') or {}
    result.update_layout(title=title,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, system-ui, sans-serif',color='#263b51',size=12),
        margin=dict(l=8,r=8,t=48,b=30),height=old_layout.get('height',360),scene=scene,
        showlegend=(len(result.data)>1 and not ('indicator' in kind)),
        legend=dict(orientation='h',x=.5,xanchor='center',y=-.04,font=dict(size=10)),
        hoverlabel=dict(bgcolor='#f5fafc',font=dict(color='#263b51')),uirevision=key,
        meta={'motion':{'key':key,'period':period,'spatial':True,'source_types':kind,'values':all_values,'version':1}})
    return result

READABLE_COLORS=['#197a91','#7862b1','#218064','#b66a29','#b44765','#3767b8','#697d39']

def label_color(label):
    import colorsys
    value=int(hashlib.sha256(str(label).casefold().encode()).hexdigest()[:8],16)
    red,green,blue=colorsys.hls_to_rgb((value%360)/360,.38,.52)
    return '#'+''.join(f'{round(c*255):02x}' for c in (red,green,blue))

def readable_figure(figure,key,period=None):
    """Preserve financial axes and values; reserve 3D for genuinely spatial data."""
    source=deepcopy(figure.to_plotly_json() if hasattr(figure,'to_plotly_json') else (figure or {}))
    traces=source.get('data') or []
    source.setdefault('data', [])
    if traces and all(t.get('type') in ('scatter3d','mesh3d','surface') for t in traces):
        return spatial_figure(source,key,period)
    result=go.Figure(source)
    if key=='cat-donut' and len(traces)==1 and traces[0].get('type')=='pie':
        labels=sequence(traces[0].get('labels'));values=sequence(traces[0].get('values'))
        rows=sorted(zip(labels,values),key=lambda row: number(row[1]) or 0)
        result=go.Figure(go.Bar(y=[str(row[0]) for row in rows],x=[row[1] for row in rows],orientation='h',
            marker_color=[label_color(row[0]) for row in rows],
            text=[money_text(number(row[1]) or 0) for row in rows],textposition='outside',cliponaxis=False,
            hovertemplate='%{y}<br>R$ %{x:,.2f}<extra></extra>'))
        result.update_layout(title='Total por categoria',height=380,xaxis_title='R$',showlegend=False)
    for i,trace in enumerate(result.data):
        typ=trace.type
        trace.uid=uid(key,str(trace.name or i))
        if typ=='bar':
            current=trace.marker.color
            # Preserve explicit semantic colors (income/expense/status).
            if current is None:trace.marker.color=READABLE_COLORS[i%len(READABLE_COLORS)]
            if key=='cat-stack':trace.marker.color=label_color(trace.name)
            trace.marker.line.width=0
        elif typ in ('scatter','scattergl'):
            if trace.line.color is None:trace.line.color=READABLE_COLORS[i%len(READABLE_COLORS)]
            trace.line.width=max(2,trace.line.width or 2)
        elif typ=='pie':
            trace.marker.colors=READABLE_COLORS
            trace.textfont.color='#203449'
            trace.textfont.size=12
            trace.automargin=True
        elif typ=='heatmap':
            trace.colorscale=[[0,'#f0f6fa'],[.5,'#75b6c3'],[1,'#176b83']]
            trace.colorbar.thickness=10
    layout=result.layout
    height=max(340,layout.height or 360)
    result.update_layout(template='plotly_white',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, Segoe UI, sans-serif',size=13,color='#203449'),
        colorway=READABLE_COLORS,margin=dict(l=60,r=48,t=56,b=72),height=height,
        title=dict(font=dict(size=15,color='#203449'),x=.02),
        legend=dict(orientation='h',x=0,y=-.19,font=dict(size=12,color='#40546b')),
        hoverlabel=dict(bgcolor='#ffffff',font=dict(color='#203449',size=13)),
        hovermode='closest',uirevision=key,separators=',.',
        transition=dict(duration=420,easing='cubic-in-out'),
        meta={'motion':{'key':key,'period':period,'spatial':False,'readable':True,'version':2}})
    if any(t.type in ('bar','scatter','scattergl','waterfall','heatmap') for t in result.data):
        result.update_xaxes(automargin=True,gridcolor='#e5edf4',zerolinecolor='#bdcbd7',tickfont=dict(size=12,color='#40546b'),title_font=dict(color='#40546b'),showline=False)
        result.update_yaxes(automargin=True,gridcolor='#e5edf4',zerolinecolor='#bdcbd7',tickfont=dict(size=12,color='#40546b'),title_font=dict(color='#40546b'),showline=False)
    if key=='cat-stack':
        result.update_layout(hovermode='x unified',bargap=.28)
        labels=[str(value) for trace in result.data for value in sequence(trace.x)]
        if len(set(labels))==1:result.update_traces(width=.35)
        result.update_xaxes(title='Dia',type='category')
        result.update_yaxes(title='R$',rangemode='tozero')
    if not result.data:
        result.add_annotation(x=.5,y=.5,xref='paper',yref='paper',text='Sem dados para o período selecionado',showarrow=False,font=dict(color='#536880',size=14))
        result.update_xaxes(visible=False);result.update_yaxes(visible=False)
    return result

def spatial_page(component,period,path='/',counter=None):
    counter=counter if counter is not None else [0]
    if isinstance(component,(list,tuple)):
        return [spatial_page(c,period,path,counter) for c in component]
    if isinstance(component,dcc.Graph):
        index=counter[0];counter[0]+=1
        key=getattr(component,'id',None) or f'{path}:chart:{index}'
        component.figure=readable_figure(getattr(component,'figure',{}) or {},str(key),period)
        component.className=((getattr(component,'className','') or '')+' spatial-chart').strip()
        component.config={**(getattr(component,'config',{}) or {}),'displaylogo':False,'responsive':True,'scrollZoom':False,'plotGlPixelRatio':1}
        component.animate=False  # 3D coordinates are interpolated by the client runtime.
    elif hasattr(component,'children'):
        component.children=spatial_page(component.children,period,path,counter)
    return component

def spatial_outputs(keys):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            result=fn(*args,**kwargs)
            period=kwargs.get('mes') or (args[0] if args and isinstance(args[0],str) else None)
            if len(keys)==1:return readable_figure(result,keys[0],period)
            values=list(result)
            for index,key in enumerate(keys):
                if key is not None:values[index]=readable_figure(values[index],key,period)
            return tuple(values)
        return wrapped
    return decorate
