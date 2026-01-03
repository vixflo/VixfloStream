Set WshShell = CreateObject("WScript.Shell")
' Restart backend (kill port 8000 if needed) without opening a visible console window.
Dim root
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Dim q
q = Chr(34)
Dim cmd
cmd = "cmd.exe /c " & q & q & root & "\restart_backend_bg.cmd" & q & q
WshShell.Run cmd, 0, False
