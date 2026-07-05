# Запускать ПОСЛЕ перезагрузки, когда wsl --install / wsl --update уже выполнены.
# Обычный (не администраторский) PowerShell.

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== 1. Проверка WSL ===" -ForegroundColor Cyan
wsl --status
if ($LASTEXITCODE -ne 0) {
    Write-Host "WSL всё ещё не готов. Запустите 'wsl --install' от администратора и перезагрузитесь." -ForegroundColor Red
    exit 1
}

Write-Host "=== 2. Запуск Docker Desktop ===" -ForegroundColor Cyan
$dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
Start-Process $dockerDesktop
Write-Host "Ждём, пока Docker Engine поднимется (до ~2 минут)..."
$ready = $false
for ($i = 0; $i -lt 24; $i++) {
    Start-Sleep -Seconds 5
    docker ps > $null 2>&1
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
}
if (-not $ready) {
    Write-Host "Docker Engine не запустился за отведённое время. Проверьте Docker Desktop вручную." -ForegroundColor Red
    exit 1
}
Write-Host "Docker Engine готов." -ForegroundColor Green

Write-Host "=== 3. Поднимаем стек (postgres + redis + qdrant + ollama) ===" -ForegroundColor Cyan
Set-Location $projectRoot
docker compose up -d

Write-Host "=== 4. Скачиваем модель phi3:mini внутрь Docker-контейнера ollama (~2.2 GB, только первый раз) ===" -ForegroundColor Cyan
docker compose exec ollama ollama pull phi3:mini

Write-Host "=== 5. Создаём .env из примера (если ещё нет) ===" -ForegroundColor Cyan
if (-not (Test-Path "$projectRoot\.env")) {
    Copy-Item "$projectRoot\.env.example" "$projectRoot\.env"
    Write-Host "Создан .env — проверьте значения перед продолжением." -ForegroundColor Yellow
} else {
    Write-Host ".env уже существует, пропускаем."
}

Write-Host "=== 6. Устанавливаем Python-зависимости ===" -ForegroundColor Cyan
pip install -r "$projectRoot\requirements.txt"

Write-Host "=== 7. Создаём демо-контакты в БД ===" -ForegroundColor Cyan
python "$projectRoot\scripts\seed_demo_data.py"

Write-Host "=== 8. Запускаем агента на демо-транскрипте ===" -ForegroundColor Cyan
Set-Location $projectRoot
python -m agents.meeting_scribe.agent --transcript "$projectRoot\tests\fixtures\demo_transcript.txt"

Write-Host "=== Готово. Проверьте результат в таблице meetings (DBeaver/psql). ===" -ForegroundColor Green
