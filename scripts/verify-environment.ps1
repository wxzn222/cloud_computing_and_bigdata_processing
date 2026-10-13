$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$pythonPath = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv first: py -3.12 -m venv .venv' }
& $pythonPath --version
& $pythonPath -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed' }
& $pythonPath -c "import platform, duckdb, pyarrow, dask, distributed, moto, sklearn, fastapi; print({'system':platform.system(),'python':platform.python_version(),'duckdb':duckdb.__version__,'pyarrow':pyarrow.__version__,'dask':dask.__version__,'moto':moto.__version__,'sklearn':sklearn.__version__})"
if ($LASTEXITCODE -ne 0) { throw 'Import check failed' }
Write-Host 'Environment check passed. This checks imports, not the optional Docker/model paths.'
