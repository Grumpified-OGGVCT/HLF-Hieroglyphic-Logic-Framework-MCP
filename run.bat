@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=stdio"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] .venv is missing. Run install.bat first. 1>&2
    exit /b 1
)

REM -- Pre-flight: check for .env, invoke wizard if missing --
if not exist ".env" (
    echo [SETUP] First run detected - no .env found.
    echo [SETUP] Launching quick setup wizard...
    %PYTHON_EXE% setup_wizard.py --quick
    if errorlevel 1 (
        echo [WARN] Setup wizard had issues. Run 'python setup_wizard.py' to configure manually.
    ) else (
        echo [OK] Configuration complete.
    )
    echo.
)

if /I "%MODE%"=="stdio" goto stdio
if /I "%MODE%"=="mcp" goto stdio
if /I "%MODE%"=="http" goto http
if /I "%MODE%"=="streamable-http" goto http
if /I "%MODE%"=="sse" goto sse
if /I "%MODE%"=="legacy-sse" goto sse
if /I "%MODE%"=="test" goto test
if /I "%MODE%"=="lint" goto lint
if /I "%MODE%"=="extension-test" goto extension_test
if /I "%MODE%"=="docker-build" goto docker_build
if /I "%MODE%"=="docker-up" goto docker_up
if /I "%MODE%"=="docker-down" goto docker_down
if /I "%MODE%"=="docker-logs" goto docker_logs
if /I "%MODE%"=="count" goto count
if /I "%MODE%"=="setup" goto setup_wizard
if /I "%MODE%"=="setup-wizard" goto setup_wizard
if /I "%MODE%"=="overwatch" goto overwatch_daemon
if /I "%MODE%"=="overwatch-daemon" goto overwatch_daemon
if /I "%MODE%"=="recursivemas" goto recursivemas
if /I "%MODE%"=="rmas" goto recursivemas
if /I "%MODE%"=="recursivemas-train" goto recursivemas_train
if /I "%MODE%"=="rmas-train" goto recursivemas_train
if /I "%MODE%"=="recursivemas-governed" goto recursivemas_governed
if /I "%MODE%"=="rmas-governed" goto recursivemas_governed
if /I "%MODE%"=="help" goto help
if /I "%MODE%"=="--help" goto help
if /I "%MODE%"=="/?" goto help

echo [ERROR] Unknown mode: %MODE% 1>&2
goto help_error

:stdio
set "HLF_TRANSPORT=stdio"
"%PYTHON_EXE%" -m hlf_mcp.server
exit /b %errorlevel%

:http
set "HLF_TRANSPORT=streamable-http"
set "HLF_HOST=127.0.0.1"
if "%~2"=="" (
    set "HLF_PORT=8123"
) else (
    set "HLF_PORT=%~2"
)
echo [RUN] Starting HLF MCP Streamable HTTP on http://%HLF_HOST%:%HLF_PORT%/mcp
"%PYTHON_EXE%" -m hlf_mcp.server
exit /b %errorlevel%

:sse
set "HLF_TRANSPORT=sse"
set "HLF_HOST=127.0.0.1"
if "%~2"=="" (
    set "HLF_PORT=8123"
) else (
    set "HLF_PORT=%~2"
)
echo [RUN] Starting legacy HLF MCP SSE compatibility transport on http://%HLF_HOST%:%HLF_PORT%
"%PYTHON_EXE%" -m hlf_mcp.server
exit /b %errorlevel%

:test
"%PYTHON_EXE%" -m pytest tests -q
exit /b %errorlevel%

:lint
"%PYTHON_EXE%" -m ruff check hlf_mcp tests
exit /b %errorlevel%

:extension_test
where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm is missing. Install Node.js LTS and run install.bat first. 1>&2
    exit /b 1
)
if not exist "extensions\hlf-vscode\node_modules" (
    echo [ERROR] VS Code bridge dependencies are missing. Run install.bat first. 1>&2
    exit /b 1
)
pushd "extensions\hlf-vscode"
call npm test
set "NPM_EXIT=%errorlevel%"
popd
exit /b %NPM_EXIT%

:count
"%PYTHON_EXE%" -c "from hlf_mcp import server; print(len(server.REGISTERED_TOOLS), len(server.REGISTERED_RESOURCES), len(server.REGISTERED_PROMPTS))"
exit /b %errorlevel%

:docker_build
where docker >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Docker is missing. Install Docker Desktop or use install.bat/run.bat stdio. 1>&2
    exit /b 1
)
docker build -t grumprolled/hlf-mcp-mouthpiece:local .
exit /b %errorlevel%

:docker_up
where docker >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Docker is missing. Install Docker Desktop or use install.bat/run.bat stdio. 1>&2
    exit /b 1
)
docker compose up -d --build hlf-mcp-mouthpiece
exit /b %errorlevel%

:docker_down
where docker >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Docker is missing. 1>&2
    exit /b 1
)
docker compose down
exit /b %errorlevel%

:docker_logs
where docker >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Docker is missing. 1>&2
    exit /b 1
)
docker logs grumprolled-hlf-mcp
exit /b %errorlevel%

:setup_wizard
"%PYTHON_EXE%" setup_wizard.py %2 %3 %4
exit /b %errorlevel%

:overwatch_daemon
echo [RUN] Starting overwatch daemon...
if exist "Dockerfile.overwatch" (
    where docker >nul 2>nul
    if not errorlevel 1 (
        echo [DOCKER] Building and starting overwatch container...
        docker build -t hlf-overwatch:latest -f Dockerfile.overwatch .
        docker run --rm --name hlf-overwatch -d hlf-overwatch:latest
        echo [OK] Overwatch daemon started in Docker.
        echo      View logs: docker logs -f hlf-overwatch
        exit /b 0
    )
)
echo [INFO] Docker not available, running overwatch in-process...
"%PYTHON_EXE%" -m hlf_mcp.hlf.overwatch_daemon
exit /b %errorlevel%

:help
echo SwarmGlass run.bat
echo.
echo Usage:
echo   run.bat                  Start MCP stdio transport (default).
echo   run.bat stdio            Same as default.
echo   run.bat http [port]      Start Streamable HTTP on 127.0.0.1, default port 8123.
echo   run.bat sse [port]       Start legacy SSE compatibility transport.
echo   run.bat test             Run pytest suite.
echo   run.bat lint             Run ruff over hlf_mcp and tests.
echo   run.bat extension-test   Run VS Code bridge/operator shell npm tests.
echo   run.bat count            Print live MCP tool/resource/prompt counts.
echo   run.bat setup            Run the configuration wizard.
echo   run.bat setup --quick    Quick setup (defaults + critical keys only).
echo   run.bat setup --validate Verify .env configuration.
echo   run.bat overwatch        Start overwatch daemon (Docker or in-process).
echo   run.bat recursivemas         Run 4-Model RecursiveMAS Ring inference (SwarmGlass governed)
echo   run.bat rmas                 Same as recursivemas (shorthand)
echo   run.bat recursivemas-train   Train CrossModelAdapters for RecursiveMAS
echo   run.bat rmas-train           Same as recursivemas-train (shorthand)
echo   run.bat recursivemas-governed Run Governed RecursiveMAS with chain-trained checkpoints
echo   run.bat rmas-governed        Same as recursivemas-governed (shorthand)
echo   run.bat docker-build     Build grumprolled/hlf-mcp-mouthpiece:local.
echo   run.bat docker-up        Build/start grumprolled-hlf-mcp on Streamable HTTP.
echo   run.bat docker-down      Stop the Docker Compose stack.
echo   run.bat docker-logs      Show grumprolled-hlf-mcp logs.
echo   run.bat help             Show this help.
exit /b 0

:help_error
echo.
echo Usage: run.bat [stdio^|http [port]^|sse [port]^|test^|lint^|extension-test^|count^|setup^|overwatch^|docker-build^|docker-up^|docker-down^|docker-logs^|help] 1>&2
exit /b 1

:recursivemas
shift
set "RMAS_ARGS=%1 %2 %3 %4 %5 %6 %7 %8 %9"
echo [RUN] 4-Model RecursiveMAS Ring with SwarmGlass governance
"%PYTHON_EXE%" -m hlf_mcp.recursivemas.inference %RMAS_ARGS%
exit /b %errorlevel%

:recursivemas_train
shift
set "RMAS_ARGS=%1 %2 %3 %4 %5 %6 %7 %8 %9"
echo [RUN] Training CrossModelAdapters for RecursiveMAS
"%PYTHON_EXE%" -m hlf_mcp.recursivemas.train %RMAS_ARGS%
exit /b %errorlevel%
:recursivemas_governed
shift
set "RMAS_ARGS=%1 %2 %3 %4 %5 %6 %7 %8 %9"
echo [RUN] Governed RecursiveMAS Pipeline (SwarmGlass governance + official chain-trained checkpoints)
"%PYTHON_EXE%" -m hlf_mcp.recursivemas.governed_pipeline %RMAS_ARGS%
exit /b %errorlevel%
