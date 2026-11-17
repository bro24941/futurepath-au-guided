@echo off
setlocal
cd /d "%~dp0" || goto folder_error
set "FP_SITE=http://127.0.0.1:8002/"
set "FP_VENV=%~dp0.venv\Scripts\python.exe"

rem Reopening the shortcut can reuse a running FuturePath session.
curl.exe --noproxy "*" --fail --silent --max-time 2 "%FP_SITE%api/health" 2>nul | findstr.exe /l /c:"futurepath-au-guided" >nul
if not errorlevel 1 goto open

"%FP_VENV%" -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 goto dependencies
echo Setting up FuturePath AU for this folder...

where.exe py.exe >nul 2>&1
if errorlevel 1 goto find_python
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto find_python
py -3 -m venv .venv
if not errorlevel 1 goto dependencies

:find_python
rem Skip the Windows Store alias. It can open the Store instead of running Python.
for /f "delims=" %%P in ('powershell.exe -NoProfile -Command "foreach ($python in @(Get-Command python.exe -All -ErrorAction SilentlyContinue)) { if ($python.Source -notlike '*\Microsoft\WindowsApps\*') { $python.Source } }"') do (
    call :make_venv "%%P"
    if not errorlevel 1 goto dependencies
)
for %%V in (313 312 311 314) do (
    call :make_venv "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    if not errorlevel 1 goto dependencies
)

rem Use the official, checksum-pinned Windows installer when Python is missing.
set "FP_ARCH=amd64"
set "FP_SHA=5da012101ba2e17113a9a1cd901e9ce1441086f2b7ecb5de06ec94163899a190"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" (
    set "FP_ARCH=arm64"
    set "FP_SHA=3089a1977c32b26f5078e5a7d0285b7a861b8c96250c5dac3b6af59fbe9e9a75"
)
echo Downloading Python for Windows. This is only needed once.
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $file=Join-Path ([IO.Path]::GetTempPath()) ('futurepath-'+[guid]::NewGuid()+'.exe'); try { $url='https://www.python.org/ftp/python/3.13.17/python-3.13.17-'+$env:FP_ARCH+'.exe'; Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $file -TimeoutSec 120; if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $env:FP_SHA) { throw 'The Python download did not match its published checksum.' }; $installer=Start-Process -FilePath $file -ArgumentList '/quiet','InstallAllUsers=0','Include_launcher=0','Include_test=0','Include_doc=0','Include_tcltk=0','Shortcuts=0','PrependPath=0' -Wait -PassThru -WindowStyle Hidden; if ($installer.ExitCode -ne 0) { throw ('Python setup exit code: '+$installer.ExitCode) } } finally { Remove-Item -LiteralPath $file -ErrorAction SilentlyContinue }"
if errorlevel 1 goto python_error
call :make_venv "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if errorlevel 1 goto python_error

:dependencies
rem pip keeps the installed packages when they already match the project.
echo Checking the website packages...
"%FP_VENV%" -m pip --disable-pip-version-check install --quiet --no-input --retries 2 --timeout 15 -r requirements.txt
if errorlevel 1 goto dependency_error

rem The server is local. Open the browser only once this app answers the health check.
set "FP_LOG_DIR=%~dp0.venv"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; Start-Process -FilePath $env:FP_VENV -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8002','--no-access-log' -WorkingDirectory (Get-Location).Path -RedirectStandardOutput (Join-Path $env:FP_LOG_DIR 'server.log') -RedirectStandardError (Join-Path $env:FP_LOG_DIR 'server-errors.log') -WindowStyle Hidden"
if errorlevel 1 goto server_error
echo Opening FuturePath AU when it is ready...
curl.exe --noproxy "*" --fail --silent --max-time 4 --retry 35 --retry-connrefused --retry-delay 1 --retry-max-time 50 "%FP_SITE%api/health" 2>nul | findstr.exe /l /c:"futurepath-au-guided" >nul
if errorlevel 1 goto server_error

:open
start "" "%FP_SITE%"
exit /b 0

:make_venv
if not exist "%~1" exit /b 1
"%~1" -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 exit /b 1
"%~1" -m venv .venv
exit /b %errorlevel%

:folder_error
echo FuturePath AU could not open the project folder. Extract the whole download and try again.
goto failed
:python_error
echo Python could not be set up. Check your internet connection or whether this PC allows software installs, then try again.
goto failed
:dependency_error
echo The website packages could not be installed. Check your internet connection and try again.
goto failed
:server_error
echo FuturePath AU did not start on port 8002. See .venv\server-errors.log in the project folder.
:failed
pause
exit /b 1
