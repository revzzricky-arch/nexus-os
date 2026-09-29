"""
NEXUS (Codename) - SandboxService Abstraction
Per review: Replace chroot assumption with SandboxService, container isolation for exec
Agents never receive unrestricted host shell/file access
Scaffold: placeholder interface only, no real exec
"""

from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
import os


class SandboxResult(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    workspace_id: str


class SandboxService(ABC):
    """
    SandboxService abstraction - scaffold
    All file/shell access goes via this service, not direct host access
    """

    @abstractmethod
    async def create_workspace(self, mission_id: str) -> str:
        """Create per-mission workspace, returns workspace path/id"""
        pass

    @abstractmethod
    async def read_file(self, mission_id: str, path: str) -> SandboxResult:
        """Read file via service, not direct host FS"""
        pass

    @abstractmethod
    async def write_file(self, mission_id: str, path: str, content: str) -> SandboxResult:
        """Write file via service, with policy enforcement"""
        pass

    @abstractmethod
    async def exec_command(
        self, mission_id: str, command: str, timeout: int = 30, env: Optional[dict] = None
    ) -> SandboxResult:
        """
        Exec command via container isolation
        MVP: ephemeral container, no network, limited CPU/mem, read-only root except workspace
        Agents never get host shell
        Scaffold: placeholder, no real exec
        """
        pass

    @abstractmethod
    async def cleanup(self, mission_id: str) -> bool:
        """Cleanup workspace"""
        pass


class PlaceholderSandboxService(SandboxService):
    """
    Placeholder implementation - scaffold only
    No real exec, no unrestricted host access
    """

    def __init__(self, workspace_root: str = "/tmp/nexus-workspaces"):
        self.workspace_root = workspace_root

    async def create_workspace(self, mission_id: str) -> str:
        # Scaffold: return placeholder path, no real creation
        return f"{self.workspace_root}/{mission_id}"

    async def read_file(self, mission_id: str, path: str) -> SandboxResult:
        # Scaffold: placeholder, no real file read
        # In real impl: enforce per-mission workspace, symlink blocking, traversal detection
        return SandboxResult(
            success=False,
            error="[Scaffold] PlaceholderSandboxService - no real file read yet",
            workspace_id=mission_id,
        )

    async def write_file(self, mission_id: str, path: str, content: str) -> SandboxResult:
        return SandboxResult(
            success=False,
            error="[Scaffold] PlaceholderSandboxService - no real file write yet",
            workspace_id=mission_id,
        )

    async def exec_command(
        self, mission_id: str, command: str, timeout: int = 30, env: Optional[dict] = None
    ) -> SandboxResult:
        # CRITICAL: No real exec in scaffold, no unrestricted host shell
        # In Phase 2: spawn ephemeral container with isolation
        return SandboxResult(
            success=False,
            error="[Scaffold] PlaceholderSandboxService - no real exec yet. Container isolation planned for Phase 2. Command blocked: "
            + command[:100],
            workspace_id=mission_id,
        )

    async def cleanup(self, mission_id: str) -> bool:
        return True


class ContainerSandboxService(SandboxService):
    """
    Future container isolation implementation - scaffold placeholder
    Would use Docker SDK to spawn ephemeral containers
    """

    def __init__(self, workspace_root: str = "/tmp/nexus-workspaces", runtime: str = "docker"):
        self.workspace_root = workspace_root
        self.runtime = runtime

    async def create_workspace(self, mission_id: str) -> str:
        return f"{self.workspace_root}/{mission_id}"

    async def read_file(self, mission_id: str, path: str) -> SandboxResult:
        return SandboxResult(
            success=False,
            error="[Scaffold] ContainerSandboxService - planned for Phase 2",
            workspace_id=mission_id,
        )

    async def write_file(self, mission_id: str, path: str, content: str) -> SandboxResult:
        return SandboxResult(
            success=False,
            error="[Scaffold] ContainerSandboxService - planned for Phase 2",
            workspace_id=mission_id,
        )

    async def exec_command(self, mission_id: str, command: str, timeout: int = 30, env=None) -> SandboxResult:
        return SandboxResult(
            success=False,
            error="[Scaffold] Container isolation planned for Phase 2 - no exec yet",
            workspace_id=mission_id,
        )

    async def cleanup(self, mission_id: str) -> bool:
        return True


def get_sandbox_service(service_type: str = "placeholder") -> SandboxService:
    from app.config import settings

    root = settings.sandbox_workspace_root
    if service_type == "container":
        return ContainerSandboxService(workspace_root=root)
    else:
        return PlaceholderSandboxService(workspace_root=root)
