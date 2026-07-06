$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Project Python interpreter not found: $python"
}

& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    throw "Unit tests failed with exit code $LASTEXITCODE"
}

& $python scripts\generate_furniture.py examples\cabinet_basic.json --name smoke_cabinet --force
if ($LASTEXITCODE -ne 0) {
    throw "Furniture CAD smoke generation failed with exit code $LASTEXITCODE"
}
