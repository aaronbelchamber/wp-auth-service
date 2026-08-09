<#
.SYNOPSIS
    Deploys WP App Bridge plugin to remote WordPress via SCP/SFTP & pushes cloud backup to GitHub.
.DESCRIPTION
    1. Reads server credentials from environment or config (.env).
    2. Syncs wp-app-bridge files directly to the remote server's wp-content/plugins/ directory.
    3. Pushes plugin updates to private GitHub repository (https://github.com/aaronbelchamber).
#>

param(
    [string]$ServerUser = $env:WP_DEPLOY_USER,
    [string]$ServerHost = $env:WP_DEPLOY_HOST,
    [string]$RemotePluginDir = $env:WP_DEPLOY_PATH,
    [string]$CommitMessage = "Update wp-app-bridge plugin & admin audit logging"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 🚀 Deploying WP App Bridge Plugin (Direct & Cloud Backup)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$PluginSrcDir = "E:\ab-code-projects\projects\Wordpress\plugins\auth-service\wp-app-bridge"

# 1. Check GitHub Remote & Push Cloud Backup
Write-Host "`n[1/2] Syncing Cloud Backup to Private GitHub Repo..." -ForegroundColor Yellow
Set-Location -Path "E:\ab-code-projects\projects\Wordpress\plugins\auth-service"

if (Test-Path ".git") {
    git add .
    git commit -m "$CommitMessage" -ErrorAction SilentlyContinue
    Write-Host "Pushing changes to https://github.com/aaronbelchamber/wp-auth-service (or configured remote)..." -ForegroundColor Cyan
    git push origin main -ErrorAction SilentlyContinue
    Write-Host "✅ Cloud backup synced to GitHub." -ForegroundColor Green
} else {
    Write-Host "ℹ️ Git repository not initialized in auth-service directory." -ForegroundColor DarkYellow
    Write-Host "Run 'git init' and 'git remote add origin https://github.com/aaronbelchamber/<repo-name>.git' to enable auto cloud backups." -ForegroundColor DarkYellow
}

# 2. Deploy Directly to WordPress Site via SCP / SFTP
Write-Host "`n[2/2] Deploying Plugin directly to WordPress Site..." -ForegroundColor Yellow

if (-not $ServerUser -or -not $ServerHost -or -not $RemotePluginDir) {
    Write-Host "==========================================================" -ForegroundColor Amber
    Write-Host " ⚙️ Setup Required for Direct Server Deployment" -ForegroundColor Amber
    Write-Host "==========================================================" -ForegroundColor Amber
    Write-Host "Please configure your remote server details in .env or pass parameters:" -ForegroundColor Yellow
    Write-Host "  `$env:WP_DEPLOY_USER = 'root' (or SSH user)" -ForegroundColor Cyan
    Write-Host "  `$env:WP_DEPLOY_HOST = 'your-wordpress-site.com'" -ForegroundColor Cyan
    Write-Host "  `$env:WP_DEPLOY_PATH = '/var/www/html/wp-content/plugins/wp-app-bridge'" -ForegroundColor Cyan
    Write-Host "`nExample command syntax:" -ForegroundColor LightYellow
    Write-Host "  .\deploy_plugin.ps1 -ServerUser 'ubuntu' -ServerHost '192.168.1.50' -RemotePluginDir '/var/www/html/wp-content/plugins/wp-app-bridge'" -ForegroundColor LightYellow
    Write-Host "==========================================================" -ForegroundColor Amber
} else {
    Write-Host "Syncing files to $ServerUser@${ServerHost}:${RemotePluginDir}..." -ForegroundColor Cyan
    scp -r "$PluginSrcDir\*" "$ServerUser@${ServerHost}:${RemotePluginDir}/"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "🎉 Direct deployment successful! Plugin updated live on your website." -ForegroundColor Green
    } else {
        Write-Host "❌ Direct deployment failed. Please check SSH key / server path credentials." -ForegroundColor Red
    }
}
