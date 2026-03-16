# HLF Fixture Gallery

Packaged fixture catalog for this repository.

The standalone repo currently carries 11 example `.hlf` programs under `fixtures/`. These are the closest packaged counterpart to the upstream `hlf_programs/` gallery.

## Current Fixtures

| Fixture | Purpose |
| --- | --- |
| `hello_world.hlf` | minimal end-to-end sanity case |
| `decision_matrix.hlf` | structured choice and reasoning flow |
| `delegation.hlf` | agent delegation pattern |
| `file_io_demo.hlf` | file-oriented workflow example |
| `log_analysis.hlf` | audit-style analysis flow |
| `module_workflow.hlf` | module/package-oriented workflow |
| `routing.hlf` | routing and orchestration example |
| `security_audit.hlf` | policy-heavy security example |
| `stack_deployment.hlf` | deployment-oriented workflow |
| `system_health_check.hlf` | health-check automation |
| `db_migration.hlf` | migration-oriented workflow |

## Running Them

```bash
uv run hlfc fixtures/hello_world.hlf
uv run hlfrun fixtures/hello_world.hlf
uv run hlftest fixtures
```

The fixture set is intentionally repo-grounded rather than a copied upstream gallery report.
