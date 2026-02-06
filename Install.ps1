Write-Host "--------------------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Executing $PSCommandPath..." -ForegroundColor Yellow
pip install --upgrade --force --no-cache-dir black
pip install --upgrade --force --no-cache-dir flake8
pip install --upgrade --force --no-cache-dir pre-commit
pip install --upgrade --force --no-cache-dir mdformat
pip install --upgrade --force --no-cache-dir coverage codecov
pre-commit install
pre-commit autoupdate
Write-Host "--------------------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Install $env:PROJECT_NAME" -ForegroundColor Yellow
if (Test-Path -Path $env:PROJECT_DIR\pyproject.toml) {pip install --no-cache-dir -e .[dev]}
