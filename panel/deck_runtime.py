"""Read-only, cached service status and weather for the LAN deck."""
import base64,json,subprocess,threading,time,urllib.request,urllib.parse
_cache={};_lock=threading.Lock();_key_locks={}
def cached(key,seconds,callback):
    with _lock:
        key_lock=_key_locks.setdefault(key,threading.Lock())
    with key_lock:
        saved=_cache.get(key)
        if saved and time.monotonic()-saved[0]<seconds:return saved[1]
        result=callback();_cache[key]=(time.monotonic(),result);return result

def status():
    def load():
        import local_runtime
        try:return local_runtime.invoke('status',timeout=20)
        except Exception:return {'gateway':'unknown','router':False,'services':[],'error':'WSL indisponível'}
    return cached('status',25,load)

def weather(city):
    city=city.strip()[:100]
    if len(city)<2:return {'ok':False,'error':'Informe a cidade'}
    def load():
        def get(url):
            with urllib.request.urlopen(url,timeout=10) as r:return json.load(r)
        geo=get('https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode({'name':city,'count':1,'language':'pt','format':'json'}))
        if not geo.get('results'):return {'ok':False,'error':'Cidade nao encontrada'}
        place=geo['results'][0]
        forecast=get('https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode({'latitude':place['latitude'],'longitude':place['longitude'],'current':'temperature_2m,wind_speed_10m','timezone':'auto'}))
        current=forecast['current']
        return {'ok':True,'city':place['name'],'temperature':current['temperature_2m'],'wind':current['wind_speed_10m'],'time':current['time'],'source':'Open-Meteo'}
    try:return cached('weather:'+city.casefold(),900,load)
    except Exception:return {'ok':False,'error':'Servico meteorologico indisponivel'}
