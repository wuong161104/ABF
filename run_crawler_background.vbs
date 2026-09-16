' ABF Universal Deep Web Crawler - Background Silent Launcher
' Chay an hoan toan khong hien cua so CMD nao

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
abfDir = currentDir & "\abf_project"
logFile = abfDir & "\crawler_bg.log"
errFile = abfDir & "\crawler_err.log"

targetUrl = InputBox("Nhap dia chi Website muon cao du lieu ngam:" & vbCrLf & _
                     "(Mac dinh: VPBank Dich vu the)", _
                     "ABF Silent Background Crawler", _
                     "https://www.vpbank.com.vn/ca-nhan/dich-vu-the")

If Trim(targetUrl) = "" Then
    WScript.Quit
End If

maxPages = InputBox("Nhap so luong trang toi da muon cao (0 = cao toan bo 100%):", _
                    "ABF Silent Background Crawler", _
                    "50")

If Trim(maxPages) = "" Then maxPages = "50"

' Chay ngam an hoan toan (0 = Hide window)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ""Start-Process python -ArgumentList 'deep_web_crawler.py --url """"" & targetUrl & """"" --max-subpages " & maxPages & " --headless' -WorkingDirectory '""" & abfDir & """' -WindowStyle Hidden -RedirectStandardOutput '""" & logFile & """' -RedirectStandardError '""" & errFile & """'"""

WshShell.Run cmd, 0, True

MsgBox "Da khoi dong Crawler chay an duoi nen thanh cong!" & vbCrLf & vbCrLf & _
       "- URL: " & targetUrl & vbCrLf & _
       "- Gioi han: " & maxPages & " trang" & vbCrLf & _
       "- Che do: Chay ngam (Khong hien cua so)" & vbCrLf & _
       "- Chong Sleep: TU DONG KICH HOAT (May khong tu dong ngu)" & vbCrLf & _
       "- Luu Realtime: Supabase DB + File tren may tinh" & vbCrLf & _
       "- File theo doi log: " & logFile, _
       64, "ABF Background Crawler Started"
