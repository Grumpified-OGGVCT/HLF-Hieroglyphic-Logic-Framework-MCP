@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "MODE=%~1"
set "PYTHON_CMD="
set "OFFLINE=0"
set "CHECK_ONLY=0"

if /I "%MODE%"=="help" goto help
if /I "%MODE%"=="--help" goto help
if /I "%MODE%"=="/?" goto help
if /I "%MODE%"=="--offline" set "OFFLINE=1"
if /I "%MODE%"=="offline" set "OFFLINE=1"
if /I "%MODE%"=="offline-check" (
    set "OFFLINE=1"
    set "CHECK_ONLY=1"
)
if /I "%MODE%"=="--offline-check" (
    set "OFFLINE=1"
    set "CHECK_ONLY=1"
)
if /I "%MODE%"=="--check" set "CHECK_ONLY=1"
if /I "%MODE%"=="check" set "CHECK_ONLY=1"

echo =========================================
echo HLF MCP Windows Install
echo =========================================
echo.

call :resolve_python
if errorlevel 1 exit /b 1

if "%CHECK_ONLY%"=="1" goto verify

if not exist ".venv\Scripts\python.exe" (
    echo [INSTALL] Creating .venv with %PYTHON_CMD% ...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv.
        exit /b 1
    )
) else (
    echo [OK] Existing .venv found.
)

echo [INSTALL] Bootstrapping pip tooling...
".venv\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 (
    echo [ERROR] Failed to bootstrap pip with ensurepip.
    exit /b 1
)
if "%OFFLINE%"=="1" (
    echo [OFFLINE] Socket-restricted install requested; skipping pip/uv upgrade so no package index is contacted.
) else (
    echo [INSTALL] Upgrading pip/setuptools/wheel/uv for online install...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel uv
    if errorlevel 1 (
        echo [WARN] Could not upgrade pip/setuptools/wheel/uv.
        echo [WARN] Continuing with locally available tooling and requirements.txt fallback.
    )
)

echo [INSTALL] Installing HLF MCP with all runtime, full, and dev dependencies...
if "%OFFLINE%"=="1" (
    call :install_python_offline
) else (
    call :install_python_online
)
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    if "%OFFLINE%"=="1" (
        echo [ERROR] Offline install did not contact the network, but required packages were not available locally.
        echo [ERROR] Action: run an online install once on this repo to seed uv/pip caches, or place wheels for requirements.txt in .\wheelhouse, then rerun install.bat --offline.
        echo [ERROR] Action: keep uv.lock with the clone when using uv's offline frozen path.
    ) else (
        echo [ERROR] Action: restore network access, repair package indexes, or pre-populate the pip/uv cache and rerun install.bat --offline.
    )
    exit /b 1
)

if not exist "db" mkdir "db"
if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"

if exist "extensions\hlf-vscode\package.json" (
    echo [INSTALL] Checking VS Code bridge/operator shell Node dependencies...
    where npm >nul 2>nul
    if errorlevel 1 (
        if exist "extensions\hlf-vscode\node_modules" (
            echo [OK] Existing VS Code bridge node_modules found; npm is not required for this verification pass.
        ) else (
            echo [ERROR] npm was not found and VS Code bridge dependencies are not installed.
            echo [ERROR] Install Node.js LTS, or restore extensions\hlf-vscode\node_modules from a prepared offline bundle, then rerun install.bat.
            exit /b 1
        )
    ) else (
        pushd "extensions\hlf-vscode"
        if "%OFFLINE%"=="1" (
            if exist "node_modules" (
                echo [OFFLINE] Existing VS Code bridge node_modules found; not running npm against any registry.
            ) else if exist "package-lock.json" (
                call npm ci --offline
            ) else (
                popd
                echo [ERROR] Offline VS Code bridge install requires package-lock.json plus npm cache, or an existing node_modules directory.
                exit /b 1
            )
        ) else if exist "package-lock.json" (
            call npm ci
        ) else (
            call npm install
        )
        if errorlevel 1 (
            popd
            echo [ERROR] VS Code bridge dependency installation failed.
            exit /b 1
        )
        popd
        echo [OK] VS Code bridge/operator shell dependencies installed.
    )
)

:verify
if not exist ".venv\Scripts\python.exe" (
    if "%OFFLINE%"=="1" (
        echo [ERROR] .venv is missing. Offline verification cannot fetch anything.
        echo [ERROR] Action: run install.bat --offline after seeding uv/pip caches or adding .\wheelhouse, or restore a prepared .venv.
    ) else (
        echo [ERROR] .venv is missing. Run install.bat first.
    )
    exit /b 1
)

echo [VERIFY] Checking package import, MCP surface, and CLI entrypoints...
".venv\Scripts\python.exe" -c "from hlf_mcp import server; print('MCP surface:', len(server.REGISTERED_TOOLS), 'tools,', len(server.REGISTERED_RESOURCES), 'resources,', len(server.REGISTERED_PROMPTS), 'prompts')"
if errorlevel 1 (
    echo [ERROR] HLF MCP import/surface check failed.
    exit /b 1
)

if exist ".venv\Scripts\hlf-mcp.exe" (
    echo [OK] hlf-mcp console script installed.
) else (
    echo [WARN] hlf-mcp console script was not found; verifying module entrypoint instead.
)
".venv\Scripts\python.exe" -c "import hlf_mcp.server; print('module entrypoint: ok')"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pytest --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pytest is missing from .venv. Run install.bat without 'check' to install full/dev dependencies.
    exit /b 1
)
".venv\Scripts\python.exe" -m ruff --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] ruff is missing from .venv. Run install.bat without 'check' to install full/dev dependencies.
    exit /b 1
)
if exist "extensions\hlf-vscode\package.json" (
    if not exist "extensions\hlf-vscode\node_modules" (
        echo [ERROR] VS Code bridge dependencies are missing.
        echo [ERROR] Action: install Node.js LTS and run install.bat, or seed npm cache and run install.bat --offline.
        exit /b 1
    )
)
if not exist ".venv\Scripts\hlf-operator.exe" (
    echo [ERROR] hlf-operator console script was not found; operator/CLI lane is not fully installed.
    echo [ERROR] Action: rerun install.bat so the editable full/dev package install completes.
    exit /b 1
)

echo.
echo =========================================
echo HLF MCP install verified.
echo.
echo MCP stdio command for local clients:
echo   %CD%\run.bat
echo.
echo Streamable HTTP command:
echo   %CD%\run.bat http 8123
echo.
echo Useful checks:
echo   run.bat count
echo   run.bat test
echo   run.bat lint
echo   run.bat extension-test
echo   run.bat docker-up
echo =========================================
exit /b 0

:resolve_python
py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.12"
    echo [OK] Found Python via py -3.12.
    exit /b 0
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    echo [OK] Found Python via python.
    exit /b 0
)

echo [ERROR] Python 3.12+ is required.
echo Install Python 3.12 or newer, then run install.bat again.
exit /b 1

:help
echo HLF MCP install.bat
echo.
echo Usage:
echo   install.bat          Install .venv, package, full/dev dependencies, and verify.
echo   install.bat --offline
echo                        Install without network/package-index access, using uv cache or .\wheelhouse.
echo   install.bat offline-check
echo                        Verify a prepared offline install without fetching anything.
echo   install.bat check    Verify an existing installation without installing.
echo   install.bat help     Show this help.
exit /b 0

:install_python_online
if exist "uv.lock" (
    ".venv\Scripts\python.exe" -m uv --version >nul 2>nul
    if not errorlevel 1 (
        echo [INSTALL] uv.lock found; attempting lock-aware frozen uv sync...
        ".venv\Scripts\python.exe" -m uv sync --frozen --extra full --extra dev
        if not errorlevel 1 exit /b 0
        echo [WARN] Frozen uv sync failed; falling back to requirements.txt compatibility path.
    ) else (
        where uv >nul 2>nul
        if not errorlevel 1 (
            echo [INSTALL] uv.lock found; attempting lock-aware frozen uv sync...
            call uv sync --frozen --extra full --extra dev
            if not errorlevel 1 exit /b 0
            echo [WARN] Frozen uv sync failed; falling back to requirements.txt compatibility path.
        )
    )
)
".venv\Scripts\python.exe" -m uv --version >nul 2>nul
if not errorlevel 1 (
    ".venv\Scripts\python.exe" -m uv pip install -r requirements.txt
    exit /b %errorlevel%
)
where uv >nul 2>nul
if not errorlevel 1 (
    call uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt
    exit /b %errorlevel%
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
exit /b %errorlevel%

:install_python_offline
if exist "uv.lock" (
    ".venv\Scripts\python.exe" -m uv --version >nul 2>nul
    if not errorlevel 1 (
        echo [OFFLINE] uv.lock found; attempting uv sync --frozen --offline from local uv cache...
        ".venv\Scripts\python.exe" -m uv sync --frozen --offline --extra full --extra dev
        if not errorlevel 1 exit /b 0
        echo [OFFLINE] uv offline sync failed; trying offline requirements fallback.
    ) else (
        where uv >nul 2>nul
        if not errorlevel 1 (
            echo [OFFLINE] uv.lock found; attempting uv sync --frozen --offline from local uv cache...
            call uv sync --frozen --offline --extra full --extra dev
            if not errorlevel 1 exit /b 0
            echo [OFFLINE] uv offline sync failed; trying offline requirements fallback.
        )
    )
)
".venv\Scripts\python.exe" -m uv --version >nul 2>nul
if not errorlevel 1 (
    echo [OFFLINE] Installing requirements from uv cache only...
    ".venv\Scripts\python.exe" -m uv pip install --offline -r requirements.txt
    if not errorlevel 1 exit /b 0
)
where uv >nul 2>nul
if not errorlevel 1 (
    echo [OFFLINE] Installing requirements from system uv cache only...
    call uv pip install --offline --python ".venv\Scripts\python.exe" -r requirements.txt
    if not errorlevel 1 exit /b 0
)
if exist "wheelhouse" (
    echo [OFFLINE] Installing requirements from .\wheelhouse with pip --no-index...
    ".venv\Scripts\python.exe" -m pip install --no-index --find-links "wheelhouse" -r requirements.txt
    exit /b %errorlevel%
)
echo [ERROR] Offline Python dependency install could not find a usable uv cache path or .\wheelhouse.
echo [ERROR] No network fetch was attempted.
echo [ERROR] Action: run install.bat once online, copy a prepared uv cache/.venv, or add wheels for every requirement to .\wheelhouse.
exit /b 1
