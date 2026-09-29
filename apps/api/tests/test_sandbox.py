"""
SandboxService Tests - Phase 2B-4
workspace creation/traversal/absolute escape/symlink escape/safe reads/writes/dangerous shell rejected
"""

import uuid
import os
import pytest
import tempfile
import shutil

from app.core.sandbox import SecureSandboxService
from app.core.exceptions import ValidationError


@pytest.fixture
def sandbox():
    base = tempfile.mkdtemp(prefix="nexus-test-sandbox-")
    service = SecureSandboxService(base_path=base)
    yield service
    shutil.rmtree(base, ignore_errors=True)


@pytest.mark.asyncio
async def test_workspace_creation(sandbox: SecureSandboxService):
    mission_id = uuid.uuid4()
    ws = await sandbox.create_workspace(mission_id)
    assert os.path.exists(ws)
    assert os.path.exists(os.path.join(ws, "output"))
    assert os.path.exists(os.path.join(ws, "tmp"))
    assert os.path.exists(os.path.join(ws, "src"))


@pytest.mark.asyncio
async def test_path_traversal_rejected(sandbox: SecureSandboxService):
    mission_id = uuid.uuid4()
    await sandbox.create_workspace(mission_id)

    with pytest.raises(ValidationError):
        sandbox.validate_path(mission_id, "../../../etc/passwd")

    with pytest.raises(ValidationError):
        sandbox.validate_path(mission_id, "output/../../etc/passwd")

    with pytest.raises(ValidationError):
        sandbox.validate_path(mission_id, "..")


@pytest.mark.asyncio
async def test_absolute_escape_rejected(sandbox: SecureSandboxService):
    mission_id = uuid.uuid4()
    await sandbox.create_workspace(mission_id)

    with pytest.raises(ValidationError):
        sandbox.validate_path(mission_id, "/etc/passwd")

    with pytest.raises(ValidationError):
        sandbox.validate_path(mission_id, "/root/.ssh/id_rsa")

    with pytest.raises(ValidationError):
        sandbox.validate_path(mission_id, "/home/user/secret")


@pytest.mark.asyncio
async def test_symlink_escape_rejected(sandbox: SecureSandboxService):
    mission_id = uuid.uuid4()
    ws = await sandbox.create_workspace(mission_id)

    # Create symlink pointing outside workspace
    outside = tempfile.mkdtemp()
    try:
        target_file = os.path.join(outside, "secret.txt")
        with open(target_file, "w") as f:
            f.write("secret")

        symlink_path = os.path.join(ws, "evil_link")
        os.symlink(target_file, symlink_path)

        # Should reject symlink that points outside
        with pytest.raises(ValidationError):
            sandbox.validate_path(mission_id, "evil_link")

    finally:
        shutil.rmtree(outside, ignore_errors=True)
        if os.path.islink(symlink_path):
            os.unlink(symlink_path)


@pytest.mark.asyncio
async def test_safe_reads_writes(sandbox: SecureSandboxService):
    mission_id = uuid.uuid4()
    await sandbox.create_workspace(mission_id)

    # Write
    result = await sandbox.write_file(mission_id, "output/test.txt", "hello world")
    assert result["success"] is True
    assert result["size"] == 11

    # Read
    content = await sandbox.read_file(mission_id, "output/test.txt")
    assert content == "hello world"

    # Write nested
    result2 = await sandbox.write_file(mission_id, "output/nested/deep/file.txt", "deep")
    assert result2["success"] is True
    content2 = await sandbox.read_file(mission_id, "output/nested/deep/file.txt")
    assert content2 == "deep"


@pytest.mark.asyncio
async def test_dangerous_shell_rejected(sandbox: SecureSandboxService):
    mission_id = uuid.uuid4()
    await sandbox.create_workspace(mission_id)

    with pytest.raises(ValidationError):
        await sandbox.exec_command(mission_id, "rm -rf /")

    with pytest.raises(ValidationError):
        await sandbox.exec_command(mission_id, ":(){:|:&};:")

    with pytest.raises(ValidationError):
        await sandbox.exec_command(mission_id, "mkfs.ext4 /dev/sda")

    with pytest.raises(ValidationError):
        await sandbox.exec_command(mission_id, "dd if=/dev/zero of=/dev/sda")

    # Safe command should work
    result = await sandbox.exec_command(mission_id, "echo hello")
    assert result["success"] is True
    assert "hello" in result["output"]


@pytest.mark.asyncio
async def test_output_limits(sandbox: SecureSandboxService):
    mission_id = uuid.uuid4()
    await sandbox.create_workspace(mission_id)

    # Too large content
    large_content = "x" * 2_000_000
    with pytest.raises(ValidationError):
        await sandbox.write_file(mission_id, "output/large.txt", large_content)
