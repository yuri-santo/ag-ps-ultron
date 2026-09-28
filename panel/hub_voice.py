import local_runtime
"""Capture only after the user presses the clearly labelled Saitama microphone."""
import io,wave,json,base64,subprocess,threading
_capture=threading.Lock()
def listen(seconds=8):
    if not _capture.acquire(blocking=False):raise ValueError('Microfone ja esta em uso pelo painel')
    try:
        import sounddevice as sd
        import numpy as np
        seconds=max(1,min(12,int(seconds)))
        audio=sd.rec(seconds*16000,samplerate=16000,channels=1,dtype='int16');sd.wait()
        if float(np.sqrt(np.mean(audio.astype(float)**2)))<70:raise ValueError('Nenhuma fala detectada no microfone do Saitama')
        stream=io.BytesIO()
        with wave.open(stream,'wb') as output:output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(audio.tobytes())
        request={'audio':base64.b64encode(stream.getvalue()).decode()}
        response=subprocess.run(local_runtime.command('transcribe'),input=json.dumps(request).encode(),capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
        response.check_returncode();result=json.loads(response.stdout)
        if not result.get('ok'):raise ValueError('Nao foi possivel reconhecer a fala')
        return result['text']
    finally:_capture.release()
