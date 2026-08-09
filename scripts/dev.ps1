param(
    [ValidateSet('setup', 'start', 'stop', 'restart')]
    [string]$Action = 'start'
)

$RootDir = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RootDir '.venv\Scripts\python.exe'
$PidFile = Join-Path $RootDir '.backend.pid'
$StdoutLog = Join-Path $RootDir '.backend.stdout.log'
$StderrLog = Join-Path $RootDir '.backend.stderr.log'

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ FilePath = 'py'; Arguments = @('-3') }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ FilePath = 'python'; Arguments = @() }
    }
    throw 'Python 3.10 or newer is required.'
}

function Invoke-Setup {
    $python = Get-PythonCommand
    & $python.FilePath @($python.Arguments + @('-m', 'venv', (Join-Path $RootDir '.venv')))
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $RootDir 'backend\requirements.txt')

    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Warning 'FFmpeg was not found on PATH.'
    }
    if (-not (Get-Command deno -ErrorAction SilentlyContinue)) {
        Write-Warning 'Deno was not found on PATH.'
    }
    Write-Host 'Setup complete.'
}

function Stop-Backend {
    if (-not (Test-Path $PidFile)) {
        Write-Host 'Backend is not running.'
        return
    }

    $pid = Get-Content $PidFile
    $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $pid -Force
        Write-Host "Stopped backend process $pid."
    } else {
        Write-Host 'Removed stale backend PID file.'
    }
    Remove-Item $PidFile -Force
}

function Start-Backend {
    if (-not (Test-Path $VenvPython)) {
        Write-Host 'Virtual environment not found. Running setup first.'
        Invoke-Setup
    }

    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile
        if (Get-Process -Id $pid -ErrorAction SilentlyContinue) {
            Write-Host "Backend is already running (PID $pid)."
            return
        }
        Remove-Item $PidFile -Force
    }

    $process = Start-Process -FilePath $VenvPython -ArgumentList 'backend\main.py' -WorkingDirectory $RootDir -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru
    Set-Content -Path $PidFile -Value $process.Id
    Write-Host "Backend started at http://127.0.0.1:8000 (PID $($process.Id))."
    Write-Host "Logs: $StdoutLog and $StderrLog"
}

switch ($Action) {
    'setup' { Invoke-Setup }
    'start' { Start-Backend }
    'stop' { Stop-Backend }
    'restart' { Stop-Backend; Start-Backend }
}
