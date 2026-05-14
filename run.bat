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

:help
echo HLF MCP run.bat
echo.
echo Usage:
echo   run.bat                 Start MCP stdio transport. MCP-safe: no stdout banner.
echo   run.bat stdio           Same as default.
echo   run.bat http [port]     Start Streamable HTTP on 127.0.0.1, default port 8123.
echo   run.bat sse [port]      Start legacy SSE compatibility transport.
echo   run.bat test            Run pytest suite.
echo   run.bat lint            Run ruff over hlf_mcp and tests.
echo   run.bat extension-test  Run VS Code bridge/operator shell npm tests.
echo   run.bat count           Print live MCP tool/resource/prompt counts.
echo   run.bat docker-build    Build grumprolled/hlf-mcp-mouthpiece:local.
echo   run.bat docker-up       Build/start grumprolled-hlf-mcp on Streamable HTTP.
echo   run.bat docker-down     Stop the Docker Compose stack.
echo   run.bat docker-logs     Show grumprolled-hlf-mcp logs.
echo   run.bat help            Show this help.
exit /b 0

:help_error
echo.
echo Usage: run.bat [stdio^|http [port]^|sse [port]^|test^|lint^|extension-test^|count^|docker-build^|docker-up^|docker-down^|docker-logs^|help] 1>&2
exit /b 1
