# Run this script AFTER installing Git from https://git-scm.com/download/win
# Right-click this file -> Run with PowerShell, or open PowerShell in this folder and run: .\connect-to-github.ps1

Set-Location $PSScriptRoot

Write-Host "Connecting this folder to GitHub (mrthomasvan-eng/multibox-planner)..." -ForegroundColor Cyan

git init
if ($LASTEXITCODE -ne 0) { Write-Host "Git not found. Install from https://git-scm.com/download/win then run this again." -ForegroundColor Red; exit 1 }

git add .
git commit -m "Connect to GitHub - local project"
git branch -M main
git remote remove origin 2>$null
git remote add origin https://github.com/mrthomasvan-eng/multibox-planner.git

Write-Host ""
Write-Host "Pushing to GitHub. You may be prompted for login." -ForegroundColor Yellow
Write-Host "Use your GitHub USERNAME and a Personal Access Token (not your password)." -ForegroundColor Yellow
Write-Host "Create a token: GitHub.com -> Settings -> Developer settings -> Personal access tokens" -ForegroundColor Yellow
Write-Host ""

git pull origin main --allow-unrelated-histories --no-edit 2>$null
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Done. Your app is connected. Future updates: git add . ; git commit -m 'message' ; git push" -ForegroundColor Green
} else {
    Write-Host "Push failed (often due to login). Run: git push -u origin main" -ForegroundColor Yellow
}
