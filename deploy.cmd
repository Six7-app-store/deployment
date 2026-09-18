@echo off
REM ======================================================================
REM  App Store - Deploy nach OpenStack (Doppelklick)
REM ----------------------------------------------------------------------
REM  Startet den Deploy in einem Container, damit auf diesem Rechner weder
REM  WSL noch Terraform oder Ansible installiert sein muss. Gebraucht wird
REM  nur Docker Desktop.
REM
REM  Vor dem ersten Mal: deploy.local.env.example nach deploy.local.env
REM  kopieren und ausfuellen. Die Datei ist gitignored.
REM ======================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo   App Store - Deploy nach OpenStack
echo   =================================
echo.

REM ---------------------------------------------------------------- Docker
docker info >nul 2>&1
if errorlevel 1 (
  echo   [FEHLER] Docker Desktop laeuft nicht.
  echo            Starte Docker Desktop und versuche es erneut.
  echo.
  pause
  exit /b 1
)
echo   [OK] Docker laeuft

REM ------------------------------------------------------------- Secrets
if not exist "deploy.local.env" (
  echo.
  echo   [FEHLER] deploy.local.env fehlt.
  echo.
  echo            Kopiere deploy.local.env.example nach deploy.local.env
  echo            und trage die Werte ein. Die Datei wird nicht committet.
  echo.
  pause
  exit /b 1
)
echo   [OK] deploy.local.env gefunden

REM Werte einlesen. Zeilen mit # werden uebersprungen.
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("deploy.local.env") do (
  if not "%%~A"=="" set "%%~A=%%~B"
)

if not defined SSH_KEY_PATH  ( echo   [FEHLER] SSH_KEY_PATH fehlt  & pause & exit /b 1 )
if not defined ENV_FILE_PATH ( echo   [FEHLER] ENV_FILE_PATH fehlt & pause & exit /b 1 )
if not exist "%SSH_KEY_PATH%"  ( echo   [FEHLER] SSH-Schluessel nicht gefunden: %SSH_KEY_PATH% & pause & exit /b 1 )
if not exist "%ENV_FILE_PATH%" ( echo   [FEHLER] .env nicht gefunden: %ENV_FILE_PATH%          & pause & exit /b 1 )
echo   [OK] Schluessel und .env gefunden

REM --------------------------------------------------------------- Modus
echo.
echo   Was soll passieren?
echo.
echo     [1] Nur ANSEHEN  - zeigt, was sich aendern wuerde (nichts wird angefasst)
echo     [2] AUSROLLEN    - wendet die Aenderungen wirklich an
echo     [3] Abbrechen
echo.
set /p CHOICE=  Auswahl (1/2/3):

if "%CHOICE%"=="3" exit /b 0
if "%CHOICE%"=="1" set MODE=plan
if "%CHOICE%"=="2" set MODE=apply
if not defined MODE (
  echo   Ungueltige Auswahl.
  pause
  exit /b 1
)

set SEED=false
if "%MODE%"=="apply" (
  echo.
  echo   Seed-Daten anlegen? Nur bei LEERER Datenbank noetig.
  echo   Im Zweifel: n
  set /p SEEDANS=  Seed-Daten anlegen (j/n)?
  if /i "!SEEDANS!"=="j" set SEED=true
)

REM --------------------------------------------------------------- Image
docker image inspect appstore-deploy:latest >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Baue das Deploy-Image ^(nur beim ersten Mal, dauert ein paar Minuten^)...
  docker build -t appstore-deploy:latest -f forgejo/job-image/Dockerfile forgejo/job-image
  if errorlevel 1 (
    echo   [FEHLER] Das Image liess sich nicht bauen.
    pause
    exit /b 1
  )
)
echo   [OK] Deploy-Image bereit

REM ----------------------------------------------------------------- Lauf
echo.
echo   Starte Deploy im Modus: %MODE%
echo   ----------------------------------------------------------------

docker run --rm -it ^
  -v "%CD%:/repo" ^
  -v "%SSH_KEY_PATH%:/run/secrets/ssh-key:ro" ^
  -e OS_AUTH_URL="%OS_AUTH_URL%" ^
  -e OS_APPLICATION_CREDENTIAL_ID="%OS_APPLICATION_CREDENTIAL_ID%" ^
  -e OS_APPLICATION_CREDENTIAL_SECRET="%OS_APPLICATION_CREDENTIAL_SECRET%" ^
  -e OS_REGION_NAME="%OS_REGION_NAME%" ^
  -e PG_CONN_STR="%PG_CONN_STR%" ^
  -e APP_HOSTNAME="%APP_HOSTNAME%" ^
  -e ANSIBLE_ROLES_PATH=/opt/ansible-roles ^
  -v "%ENV_FILE_PATH%:/run/secrets/stack-env:ro" ^
  -w /repo ^
  appstore-deploy:latest ^
  bash scripts/deploy.sh %MODE% %SEED%

set RC=%ERRORLEVEL%
echo   ----------------------------------------------------------------
if "%RC%"=="0" (
  echo   Fertig.
) else (
  echo   Der Deploy wurde abgebrochen ^(Code %RC%^). Meldung oben lesen.
)
echo.
pause
exit /b %RC%
