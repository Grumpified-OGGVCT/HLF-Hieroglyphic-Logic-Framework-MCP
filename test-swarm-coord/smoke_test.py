import sys
import sys
from pathlib import Path
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
from hlf_mcp.hlf.agent_spawner import AgentSpawner

spawner = AgentSpawner(backend='subprocess', model='deepseek-v4-pro:cloud')
handle = spawner.spawn(
    agent_id='SmokeTest',
    role='SchemaDesigner',
    task='Write a PostgreSQL CREATE TABLE users statement. Return ONLY JSON: {"schema.sql": "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL);"}',
    model='deepseek-v4-pro:cloud'
)
print('Spawned agent', handle.agent_id, 'PID', handle.pid, 'work_dir', handle.work_dir)
result = spawner.wait(handle.agent_id, timeout=60)
print('Status:', result.status)
print('Elapsed ms:', result.elapsed_ms)
print('Tokens:', result.tokens_used)
print('Files:', result.files_written)
print('Stdout:', result.stdout[:200])
if result.error:
    print('Error:', result.error)
