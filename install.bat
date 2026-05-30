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
if /I "%MODE%"=="--no-wizard" set "SKIP_WIZARD=1"

echo =========================================
echo   SwarmGlass - Universal AI Governance
echo   install.bat
echo =========================================
echo.

call :resolve_python
if errorlevel 1 exit /b 1

if "%CHECK_ONLY%"=="1" goto verify

REM -- Pre-flight: run setup wizard if .env is missing --
if "%SKIP_WIZARD%"=="1" goto skip_wizard
if exist ".env" goto skip_wizard
echo [SETUP] No .env found. Launching setup wizard...
%PYTHON_CMD% setup_wizard.py --quick
if errorlevel 1 (
    echo [WARN] Setup wizard exited with error. Continuing with defaults.
    echo [WARN] Run 'python setup_wizard.py' later to configure manually.
) else (
    echo [OK] .env created with your configuration.
)
:skip_wizard

REM -- Detect Docker for overwatch --
where docker >nul 2>nul
if not errorlevel 1 (
    echo [OK] Docker detected - overwatch container support enabled.
) else (
    echo [INFO] Docker not found - overwatch will run in-process (install Docker for daemon mode).
)

if not exist ".venv\Scripts\python.exe" (
    echo [INSTALL] Creating .venv with %PYTHON_CMD% ...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv.
        echo [FIX] Ensure Python 3.12+ is installed and on PATH.
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

echo [INSTALL] Installing SwarmGlass with all runtime, full, and dev dependencies...
if "%OFFLINE%"=="1" (
    call :install_python_offline
) else (
    call :install_python_online
)
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    if "%OFFLINE%"=="1" (
        echo [ERROR] Offline install did not contact the network, but required packages were not available locally.
        echo [FIX] Run an online install once to seed uv/pip caches, or place wheels for requirements.txt in .\wheelhouse, then rerun install.bat --offline.
        echo [FIX] Keep uv.lock with the clone when using uv's offline frozen path.
    ) else (
        echo [FIX] Restore network access, repair package indexes, or pre-populate the pip/uv cache and rerun install.bat --offline.
    )
    exit /b 1
)

if not exist "db" mkdir "db"
if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"
if not exist "state" mkdir "state"

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
        echo [FIX] Run install.bat --offline after seeding uv/pip caches or adding .\wheelhouse, or restore a prepared .venv.
    ) else (
        echo [ERROR] .venv is missing. Run install.bat first.
    )
    exit /b 1
)

echo [VERIFY] Checking package import, MCP surface, and CLI entrypoints...
".venv\Scripts\python.exe" -c "from hlf_mcp import server; print('MCP surface:', len(server.REGISTERED_TOOLS), 'tools,', len(server.REGISTERED_RESOURCES), 'resources,', len(server.REGISTERED_PROMPTS), 'prompts')"
if errorlevel 1 (
    echo [ERROR] SwarmGlass MCP import/surface check failed.
    exit /b 1
)

REM -- Verify CLI entrypoints --
set "MISSING_CLI=0"
for %%c in (hlf-mcp hlf-operator hlfc hlffmt hlflint hlfpm hlfrun hlfsh hlflsp hlftest hlf-test-runner hlf-evidence hlf-bench) do (
    if not exist ".venv\Scripts\%%c.exe" (
        echo [WARN] %%c console script not found
        set "MISSING_CLI=1"
    )
)
if "%MISSING_CLI%"=="1" (
    echo [WARN] Some CLI entrypoints are missing. The package may not be fully installed.
    echo [FIX] Rerun install.bat without --check to perform a full install.
)
".venv\Scripts\python.exe" -c "import hlf_mcp.server; print('module entrypoint: ok')" >nul 2>&1
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pytest is missing from .venv. Run install.bat without 'check' to install full/dev dependencies.
    exit /b 1
)
".venv\Scripts\python.exe" -m ruff --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ruff is missing from .venv. Run install.bat without 'check' to install full/dev dependencies.
    exit /b 1
)
if exist "extensions\hlf-vscode\package.json" (
    if not exist "extensions\hlf-vscode\node_modules" (
        echo [ERROR] VS Code bridge dependencies are missing.
        echo [FIX] Install Node.js LTS and run install.bat, or seed npm cache and run install.bat --offline.
        exit /b 1
    )
)

REM -- Build overwatch container if Docker is available --
where docker >nul 2>nul
if not errorlevel 1 (
    if exist "Dockerfile.overwatch" (
        echo [DOCKER] Building overwatch container...
        docker build -t hlf-overwatch:latest -f Dockerfile.overwatch .
        if errorlevel 1 (
            echo [WARN] Overwatch container build failed - daemon will fall back to in-process mode.
        ) else (
            echo [OK] Overwatch container built: hlf-overwatch:latest
        )
    )
)

echo.
echo =========================================
echo   SwarmGlass install verified.
echo.
echo   Quick start:
echo     run.bat              Start MCP stdio server
echo     run.bat http 8123    Start HTTP server
echo     run.bat count        Show tool counts
echo     run.bat test         Run test suite
echo     run.bat help         Show all commands
echo.
echo   Documentation:
echo     docs\SWARMGLASS_EXPLAINER.md    Full architecture explainer
echo     docs\AGENT_USAGE_GUIDE.md       Agent onboarding guide
echo     docs\AGENTS_CATALOG.md          Complete tool catalog
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
echo SwarmGlass install.bat
echo.
echo Usage:
echo   install.bat             Install .venv, package, full/dev dependencies, and verify.
echo                            Also launches setup wizard if .env is missing.
echo   install.bat --no-wizard  Skip the setup wizard even if .env is missing.
echo   install.bat --offline    Install without network/package-index access, using uv cache or .\wheelhouse.
echo   install.bat offline-check Verify a prepared offline install without fetching anything.
echo   install.bat check        Verify an existing installation without installing.
echo   install.bat help         Show this help.
echo.
echo After install:
echo   python setup_wizard.py           Re-run the configuration wizard
echo   python setup_wizard.py --quick   Quick setup (defaults + critical keys only)
echo   python setup_wizard.py --validate Check your .env for issues
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
echo [FIX] Run install.bat once online, copy a prepared uv cache/.venv, or add wheels for every requirement to .\wheelhouse.
exit /b 1
