"""Read/write the real Windows default audio endpoint, one COM context per request."""
def volume(action='status',value=None):
    import comtypes
    from pycaw.pycaw import AudioUtilities
    comtypes.CoInitialize()
    try:
        endpoint=AudioUtilities.GetSpeakers().EndpointVolume
        if action=='set':endpoint.SetMasterVolumeLevelScalar(max(0,min(100,float(value)))/100,None)
        elif action=='mute':endpoint.SetMute(not endpoint.GetMute(),None)
        elif action in ('up','down'):
            endpoint.SetMasterVolumeLevelScalar(max(0,min(1,endpoint.GetMasterVolumeLevelScalar()+(.05 if action=='up' else -.05))),None)
        return {'ok':True,'volume':round(endpoint.GetMasterVolumeLevelScalar()*100),'muted':bool(endpoint.GetMute())}
    except Exception as exc:return {'ok':False,'error':type(exc).__name__}
    finally:comtypes.CoUninitialize()
