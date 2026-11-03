param([string]$Name = '吉球')
$ErrorActionPreference = 'Stop'
$originalPath = $env:Path
try {
    # Avoid picking up unrelated DLLs from other applications during analysis.
    $env:Path = "$env:SystemRoot\System32;$env:SystemRoot"
    & "$PSScriptRoot\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name $Name --icon "$PSScriptRoot\assets\jiqiu.ico" --add-data "$PSScriptRoot\assets\jiqiu.png;assets" --add-data "$PSScriptRoot\data\history.sqlite3;data" --add-data "$PSScriptRoot\assets\celebration.wav;assets" --add-data "$PSScriptRoot\assets\rolling.wav;assets" --add-data "$PSScriptRoot\assets\complete.wav;assets" "$PSScriptRoot\main.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
} finally {
    $env:Path = $originalPath
}
