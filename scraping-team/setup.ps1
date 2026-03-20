# setup.ps1
Write-Host "--- Starting Scraping Team Environment Setup ---" -ForegroundColor Cyan

# 1. Create Virtual Environment
Write-Host "Step 1: Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

# 2. Upgrade Pip in the venv
Write-Host "Step 2: Upgrading pip..." -ForegroundColor Yellow
.\venv\Scripts\python.exe -m pip install --upgrade pip

# 3. Install Dependencies
Write-Host "Step 3: Installing dependencies from requirements.txt..." -ForegroundColor Yellow
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. Create VS Code folder if it doesn't exist
if (!(Test-Path .vscode)) { New-Item -ItemType Directory -Path .vscode }

# 5. Create launch.json for easy debugging
Write-Host "Step 4: Configuring VS Code Debugger..." -ForegroundColor Yellow
$launchJson = @'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File (Scraping Team)",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "python": "${workspaceFolder}/venv/Scripts/python.exe",
            "justMyCode": true
        }
    ]
}
'@
$launchJson | Out-File -FilePath .vscode\launch.json -Encoding utf8

Write-Host "--- SETUP COMPLETE ---" -ForegroundColor Green
Write-Host "To start working:" -ForegroundColor White
Write-Host "1. Open VS Code" -ForegroundColor White
Write-Host "2. Press Ctrl+Shift+P and select 'Python: Select Interpreter'" -ForegroundColor White
Write-Host "3. Choose the one inside .\venv\Scripts\" -ForegroundColor White
pause