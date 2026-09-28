' Ancora do WSL para o Hermes/Ultron.
'
' Por que um .vbs e nao o wsl.exe direto na tarefa agendada:
' chamar wsl.exe direto abre uma janela de console visivel. Fechar essa janela
' mata a ancora (codigo 0xC000013A, STATUS_CONTROL_C_EXIT) e derruba o
' hermes-gateway junto com a distro. O Run(..., 0, False) abaixo roda com a
' janela oculta, entao nao ha o que fechar por engano.
'
' O processo precisa ser persistente: sem ele o WSL desliga a distro assim que
' o ultimo comando termina.
'
' 28/09/2026: no logon o Windows as vezes nega o wsl.exe por alguns segundos
' (WSL/Store ainda subindo ou atualizando) e o script antigo mostrava
' "Permissao negada" (800A0046, linha 14). Agora:
'   - usa o caminho completo do wsl.exe;
'   - tenta de novo por ~3 minutos, sem janela de erro;
'   - nao cria ancora duplicada se ja houver uma rodando;
'   - registra o que aconteceu em %LOCALAPPDATA%\hermes-autostart.log;
'   - termina com codigo 1 se nao conseguir, para a tarefa agendada repetir.
' Teste sem efeito: cscript //nologo "%USERPROFILE%\.hermes-autostart.vbs" /check

Option Explicit

Const TENTATIVAS = 18
Const ESPERA_MS = 10000
Const LOG_MAX = 262144

Dim shell, fso, logPath, wslExe, i, checkOnly, rc, desc

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
logPath = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\hermes-autostart.log"
checkOnly = False
If WScript.Arguments.Count > 0 Then checkOnly = (LCase(WScript.Arguments(0)) = "/check")

Sub Registrar(texto)
    Dim f
    On Error Resume Next
    If fso.FileExists(logPath) Then
        If fso.GetFile(logPath).Size > LOG_MAX Then
            fso.CopyFile logPath, logPath & ".old", True
            fso.DeleteFile logPath, True
        End If
    End If
    Err.Clear
    Set f = fso.OpenTextFile(logPath, 8, True)
    If Err.Number = 0 Then
        f.WriteLine Now & "  " & texto
        f.Close
    End If
    Err.Clear
    On Error GoTo 0
    If checkOnly Then WScript.Echo texto
End Sub

Function CaminhoWsl()
    Dim candidatos, c
    candidatos = Array( _
        shell.ExpandEnvironmentStrings("%SystemRoot%") & "\Sysnative\wsl.exe", _
        shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wsl.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\WSL\wsl.exe")
    For Each c In candidatos
        If fso.FileExists(c) Then
            CaminhoWsl = c
            Exit Function
        End If
    Next
    CaminhoWsl = "wsl.exe"
End Function

Function AncoraAtiva()
    Dim wmi, lista
    AncoraAtiva = False
    On Error Resume Next
    Set wmi = GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")
    If Err.Number = 0 Then
        Set lista = wmi.ExecQuery("SELECT ProcessId FROM Win32_Process WHERE Name='wsl.exe' AND CommandLine LIKE '%sleep infinity%'")
        If Err.Number = 0 Then
            If lista.Count > 0 Then AncoraAtiva = True
        End If
    End If
    Err.Clear
    On Error GoTo 0
End Function

wslExe = CaminhoWsl()

If checkOnly Then
    Registrar "check: wsl=" & wslExe & " ancora_ativa=" & AncoraAtiva() & " log=" & logPath
    WScript.Quit 0
End If

If AncoraAtiva() Then
    Registrar "ancora ja ativa; nada a fazer"
    WScript.Quit 0
End If

For i = 1 To TENTATIVAS
    On Error Resume Next
    Err.Clear
    shell.Run """" & wslExe & """ -d Debian -u root --exec /usr/bin/sleep infinity", 0, False
    rc = Err.Number
    desc = Err.Description
    Err.Clear
    On Error GoTo 0
    If rc = 0 Then
        WScript.Sleep 5000
        If AncoraAtiva() Then
            Registrar "ancora iniciada (tentativa " & i & ", " & wslExe & ")"
            WScript.Quit 0
        End If
        Registrar "tentativa " & i & ": wsl.exe abriu mas a ancora nao ficou ativa"
    Else
        Registrar "tentativa " & i & ": erro " & rc & " (" & desc & ") ao iniciar " & wslExe
    End If
    WScript.Sleep ESPERA_MS
Next

Registrar "falhou apos " & TENTATIVAS & " tentativas; a tarefa agendada vai repetir"
WScript.Quit 1
