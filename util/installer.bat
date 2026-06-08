@echo off
REM ============================================================
REM EMS - Installeur local
REM Copie les .exe EMS sur le poste pour un demarrage rapide
REM ============================================================

setlocal enableextensions

set "SRC=%~dp0"
set "DST=%LOCALAPPDATA%\EMS_Apps"

echo.
echo ========================================
echo   EMS - Installation locale
echo ========================================
echo.
echo Source : %SRC%
echo Destination : %DST%
echo.

if not exist "%DST%" mkdir "%DST%"

echo Copie des .exe et config en cours, merci de patienter...
echo.

REM Copier config.ini et tous les EMS_*.exe
robocopy "%SRC%" "%DST%" "config.ini" "EMS_*.exe" /NJH /NJS /NDL /NC /NS

echo.
echo ========================================
echo   Creation des raccourcis Bureau
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $desk=[Environment]::GetFolderPath('Desktop'); foreach($app in 'EMS_Launcher','EMS_Bons','EMS_Parc','EMS_Garanties','EMS_Amelioration','EMS_BI','EMS_Pieces') { $exe=Join-Path $env:LOCALAPPDATA ('EMS_Apps\'+$app+'.exe'); if (Test-Path $exe) { $lnk=$ws.CreateShortcut((Join-Path $desk ($app+'.lnk'))); $lnk.TargetPath=$exe; $lnk.WorkingDirectory=(Split-Path $exe); $lnk.IconLocation=$exe; $lnk.Save(); Write-Host ('  Raccourci cree : '+$app) } else { Write-Host ('  (non trouve : '+$app+'.exe)') } }"

echo.
echo ========================================
echo   Installation terminee
echo ========================================
echo.
echo Vous pouvez maintenant lancer les applications depuis le Bureau.
echo.
pause
