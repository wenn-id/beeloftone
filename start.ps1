param(
    [string]$Python,
    [switch]$Demo,
    [switch]$SetupOnly,
    [ValidateRange(1024, 65535)][int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $runtime = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $runtime)) {
        if (-not $Python) {
            $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
            if (Test-Path -LiteralPath $bundledPython) {
                $Python = $bundledPython
            } elseif (Get-Command python -ErrorAction SilentlyContinue) {
                $Python = (Get-Command python).Source
            } else {
                throw 'Python 3.12+ diperlukan. Jalankan .\start.ps1 -Python C:\path\python.exe'
            }
        }
        & $Python -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'
        if ($LASTEXITCODE -ne 0) { throw 'Gunakan Python 3.12 atau lebih baru.' }
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Pembuatan virtual environment gagal.' }
    }
    & $runtime -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Instalasi dependencies gagal.' }
    & $runtime -m pip install --disable-pip-version-check --no-deps -e .
    if ($LASTEXITCODE -ne 0) { throw 'Instalasi Beeloft gagal.' }
    if ($SetupOnly) { return }

    $database = if ($Demo) { 'data/demo.sqlite3' } else { 'data/beeloft.sqlite3' }
    if (-not (Test-Path -LiteralPath $database)) {
        if ($Demo) {
            & $runtime -m beeloft --db $database demo
        } else {
            & $runtime -m beeloft --db $database user --name 'Pemilik' --role admin
        }
        if ($LASTEXITCODE -ne 0) { throw 'Inisialisasi database gagal.' }
        Write-Host 'Simpan API key di atas. Masukkan pada kolom Kunci akses di dashboard.'
    }
    Write-Host "Beeloft dashboard: http://127.0.0.1:$Port/ | API: /docs | Database: $database | Ctrl+C untuk berhenti"
    & $runtime -m beeloft --db $database serve --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Server berhenti dengan error.' }
} finally {
    Pop-Location
}
