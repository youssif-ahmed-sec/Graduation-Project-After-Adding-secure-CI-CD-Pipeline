[Setup]
AppName=FileTrack EDR Agent
AppVersion=1.0
DefaultDirName={autopf}\FileTrack Agent
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=userdocs:InnoSetupOutput
OutputBaseFilename=FileTrack_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "D:\Graduation Project\agent-filetrack\dist\FileTrack_Agent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

Source: "D:\Graduation Project\agent-filetrack\config.json"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "autostartup"; Description: "Run FileTrack Agent automatically on Windows startup (Stealth Mode & Highest Privileges)"; GroupDescription: "Security Engine Options:"; Flags: checkedonce

[Run]
Filename: "{app}\FileTrack_Agent.exe"; Description: "Launch FileTrack EDR Engine Now"; Flags: nowait postinstall skipifsilent shellexec
Filename: "{sys}\schtasks.exe"; Parameters: "/create /tn ""FileTrack_Agent_Startup"" /tr ""\""{app}\FileTrack_Agent.exe\"""" /sc onlogon /rl highest /f"; Tasks: autostartup; Flags: runhidden

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/delete /tn ""FileTrack_Agent_Startup"" /f"; Flags: runhidden