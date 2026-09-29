"""
Migration Tests - PR 2B-1
Test database migration upgrade/downgrade
"""

import pathlib
import re


MIGRATIONS_DIR = pathlib.Path(__file__).parent.parent / "app" / "db" / "migrations" / "versions"


def test_migration_file_exists():
    """Migration file for phase2b persistence foundation should exist"""
    files = list(MIGRATIONS_DIR.glob("*.py"))
    assert len(files) >= 1, f"No migration files found in {MIGRATIONS_DIR}"
    
    # Find our specific migration
    found = False
    for f in files:
        if "phase2b" in f.name.lower() and "persistence" in f.name.lower():
            found = True
            break
    assert found, f"Expected phase2b persistence foundation migration not found, got {files}"


def test_migration_has_upgrade_downgrade():
    """Migration should have upgrade and downgrade functions"""
    migration_file = MIGRATIONS_DIR / "001_phase2b_persistence_foundation.py"
    assert migration_file.exists(), f"Migration file {migration_file} not found"
    
    content = migration_file.read_text()
    assert "def upgrade()" in content, "upgrade() not found in migration"
    assert "def downgrade()" in content, "downgrade() not found in migration"
    assert "users" in content, "users table not in migration"
    assert "missions" in content, "missions table not in migration"
    assert "tasks" in content, "tasks table not in migration"
    assert "task_dependencies" in content, "task_dependencies table not in migration"
    assert "agents" in content, "agents table not in migration"
    assert "agent_runs" in content, "agent_runs table not in migration"
    assert "events" in content, "events table not in migration"
    
    # Check for fix: agent_id FK -> agents.id, agent_run_id FK -> agent_runs.id
    assert "agent_id" in content, "agent_id not in events migration"
    assert "agent_run_id" in content, "agent_run_id not in events migration - required per review fix"
    assert 'ForeignKey("agents.id"' in content or "agents.id" in content, "agent_id should FK to agents.id"
    assert 'ForeignKey("agent_runs.id"' in content or "agent_runs.id" in content, "agent_run_id should FK to agent_runs.id"


def test_migration_deferred_tables_not_included():
    """PR 2B-1 must defer tool_registry, mcp_servers, tool_permissions, tool_calls, approvals, audit_logs"""
    migration_file = MIGRATIONS_DIR / "001_phase2b_persistence_foundation.py"
    content = migration_file.read_text()
    
    deferred = ["tool_registry", "mcp_servers", "tool_permissions", "tool_calls", "approvals", "audit_logs"]
    for table in deferred:
        # Should NOT be in this minimal migration unless concrete dependency
        # Check that we don't create these tables
        pattern = rf'create_table\(\s*"{table}"'
        matches = re.findall(pattern, content)
        assert len(matches) == 0, f"Deferred table {table} should NOT be in PR 2B-1 migration (genuinely small)"


def test_migration_has_pgcrypto_extension():
    """Migration should enable pgcrypto for gen_random_uuid"""
    migration_file = MIGRATIONS_DIR / "001_phase2b_persistence_foundation.py"
    content = migration_file.read_text()
    assert "pgcrypto" in content, "pgcrypto extension not enabled for gen_random_uuid"


def test_alembic_ini_exists():
    """alembic.ini should exist and have correct config"""
    ini_path = pathlib.Path(__file__).parent.parent / "alembic.ini"
    assert ini_path.exists(), "alembic.ini not found"
    content = ini_path.read_text()
    assert "script_location" in content
    assert "app/db/migrations" in content
    assert "sqlalchemy.url" in content


def test_env_py_async():
    """env.py should be async and import Base metadata"""
    env_path = pathlib.Path(__file__).parent.parent / "app" / "db" / "migrations" / "env.py"
    assert env_path.exists()
    content = env_path.read_text()
    assert "async_engine_from_config" in content, "env.py should use async engine"
    assert "Base.metadata" in content, "env.py should use Base.metadata"
    assert "target_metadata" in content
