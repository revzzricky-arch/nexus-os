"""
SandboxService - Secure workspace-scoped file operations
Phase 2B-4 implementation with deterministic non-executing stub for exec

Security requirements:
- No unrestricted host FS
- No host shell
- Workspace-scoped only
- Reject path traversal, unsafe symlink, absolute outside workspace
- Normalize/validate paths
- Shell routed via SandboxService requires approval via PermissionService
- Isolated execution abstraction - deterministic non-executing stub for MVP
- Do NOT use os.system, shell=True, unrestricted subprocess, eval/exec/compile
- No dangerous demo exec
- Real container isolation deferred to future phase with Docker SDK

Execution Boundary Clarification:
- exec_command() is a DETERMINISTIC NON-EXECUTING STUB in Phase 2B-4
- It does NOT execute commands on host via subprocess.run
- It does NOT claim to be actual container isolation
- It validates command against forbidden patterns and returns simulated result
- Real Docker container isolation will be implemented in future phase using Docker SDK
- This is documented as deferred boundary, safe for tests and CI
"""

import os
import re
import uuid
import tempfile
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from app.core.exceptions import ValidationError


class SandboxService(ABC):
    """
    Abstract SandboxService interface
    """

    @abstractmethod
    async def create_workspace(self, mission_id: uuid.UUID) -> str:
        pass

    @abstractmethod
    async def read_file(self, mission_id: uuid.UUID, path: str) -> str:
        pass

    @abstractmethod
    async def write_file(self, mission_id: uuid.UUID, path: str, content: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def exec_command(self, mission_id: uuid.UUID, command: str, timeout: int = 30) -> Dict[str, Any]:
        pass

    @abstractmethod
    def validate_path(self, mission_id: uuid.UUID, path: str) -> str:
        """Returns normalized safe path or raises ValidationError"""
        pass

    async def cleanup(self, mission_id: uuid.UUID) -> bool:
        """Cleanup workspace - optional for compatibility"""
        return True


class SecureSandboxService(SandboxService):
    """
    Secure implementation with path normalization, traversal protection, symlink protection
    and deterministic non-executing stub for exec_command

    Security model:
    - All operations scoped to workspace root / mission-specific subdir
    - Path normalization via os.path.normpath
    - Reject .. components that escape workspace
    - Reject absolute paths outside workspace
    - Reject unsafe symlinks (symlinks that point outside workspace)
    - No os.system, no shell=True, no subprocess.run - exec is deterministic stub
    - Output limits enforced
    - Deterministic for tests - uses temp directory or /tmp/nexus-sandbox/{mission_id} abstraction

    Execution Boundary:
    - exec_command does NOT execute on host
    - Returns deterministic stub result
    - Real container isolation deferred to future Docker SDK implementation
    - Never claims simulated execution is actual isolation
    """

    # Dangerous patterns that must never be executed even via future container abstraction
    FORBIDDEN_COMMAND_PATTERNS = [
        r"rm\s+-rf\s+/",  # rm -rf /
        r":\(\)\{\s*:\|\:&\s*\};:",  # fork bomb
        r"mkfs\.",
        r"dd\s+if=.*of=/dev/",
        r">\s*/dev/sd",
        r"chmod\s+.*\s+/",
        r"mv\s+.*\s+/",
    ]

    # Dangerous substrings that are always rejected
    FORBIDDEN_SUBSTRINGS = [
        "rm -rf /",
        "mkfs",
        "> /dev",
        ":(){",
    ]

    def __init__(self, base_path: Optional[str] = None):
        # Base path for workspaces - defaults to temp or /tmp/nexus-sandbox
        # In Docker Compose, this would be volume-mounted isolation
        # Try to get from config if available, else temp
        if base_path is None:
            try:
                from app.config import settings
                base_path = getattr(settings, "sandbox_workspace_root", None)
            except Exception:
                base_path = None
        self.base_path = base_path or os.path.join(tempfile.gettempdir(), "nexus-sandbox")
        os.makedirs(self.base_path, exist_ok=True)

    def _get_workspace_root(self, mission_id: uuid.UUID) -> str:
        return os.path.join(self.base_path, str(mission_id))

    def validate_path(self, mission_id: uuid.UUID, path: str) -> str:
        """
        Validate and normalize path, ensure workspace-scoped
        Raises ValidationError if traversal, absolute escape, or unsafe symlink detected
        """
        if not path or not isinstance(path, str):
            raise ValidationError("Invalid path: must be non-empty string")

        # Reject null bytes
        if "\x00" in path:
            raise ValidationError("Invalid path: contains null byte")

        path = path.strip()

        # Reject absolute paths that are outside workspace concept
        if os.path.isabs(path):
            system_abs_prefixes = ["/etc", "/usr", "/bin", "/sbin", "/root", "/home", "/var", "/tmp", "/dev", "/proc"]
            for prefix in system_abs_prefixes:
                if path.startswith(prefix + "/") or path == prefix:
                    raise ValidationError(f"Absolute path outside workspace forbidden: {path}", details={"path": path})

        # Normalize to remove . and .. components
        normalized = os.path.normpath(path)

        workspace_root = self._get_workspace_root(mission_id)
        candidate = os.path.join(workspace_root, normalized.lstrip("/"))
        candidate_normalized = os.path.normpath(candidate)

        # Ensure candidate is inside workspace_root
        try:
            workspace_abs = os.path.abspath(workspace_root)
            candidate_abs = os.path.abspath(candidate_normalized)
            common = os.path.commonpath([workspace_abs, candidate_abs])
            if common != workspace_abs:
                raise ValidationError(
                    f"Path traversal detected: {path} escapes workspace",
                    details={"path": path, "normalized": normalized},
                )
        except ValueError as e:
            raise ValidationError(f"Invalid path: {path}", details={"error": str(e)})

        # Check for symlink escape - if path exists and is symlink, verify target inside workspace
        if os.path.islink(candidate_abs):
            target = os.readlink(candidate_abs)
            if os.path.isabs(target):
                target_abs = os.path.abspath(target)
                try:
                    common = os.path.commonpath([workspace_abs, target_abs])
                    if common != workspace_abs:
                        raise ValidationError(
                            f"Unsafe symlink: {path} points outside workspace to {target}",
                            details={"path": path, "symlink_target": target},
                        )
                except ValueError:
                    raise ValidationError(f"Unsafe symlink: {path}", details={"path": path})
            else:
                link_dir = os.path.dirname(candidate_abs)
                resolved = os.path.normpath(os.path.join(link_dir, target))
                resolved_abs = os.path.abspath(resolved)
                try:
                    common = os.path.commonpath([workspace_abs, resolved_abs])
                    if common != workspace_abs:
                        raise ValidationError(
                            f"Unsafe symlink: {path} points outside workspace",
                            details={"path": path, "symlink_target": target},
                        )
                except ValueError:
                    raise ValidationError(f"Unsafe symlink: {path}", details={"path": path})

        return candidate_abs

    async def create_workspace(self, mission_id: uuid.UUID) -> str:
        workspace_root = self._get_workspace_root(mission_id)
        os.makedirs(workspace_root, exist_ok=True)
        for subdir in ["output", "tmp", "src"]:
            os.makedirs(os.path.join(workspace_root, subdir), exist_ok=True)
        return workspace_root

    async def read_file(self, mission_id: uuid.UUID, path: str) -> str:
        safe_path = self.validate_path(mission_id, path)

        if not os.path.exists(safe_path):
            raise ValidationError(f"File not found: {path}", details={"path": path})

        if not os.path.isfile(safe_path):
            raise ValidationError(f"Path is not a file: {path}", details={"path": path})

        size = os.path.getsize(safe_path)
        if size > 1_000_000:
            raise ValidationError(f"File too large: {size} bytes, limit 1MB", details={"path": path, "size": size})

        try:
            with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if len(content) > 1_000_000:
                    content = content[:1_000_000] + "\n...[truncated]"
                return content
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Failed to read file {path}: {str(e)}", details={"path": path})

    async def write_file(self, mission_id: uuid.UUID, path: str, content: str) -> Dict[str, Any]:
        safe_path = self.validate_path(mission_id, path)

        if len(content) > 1_000_000:
            raise ValidationError("Content too large, limit 1MB", details={"size": len(content)})

        parent = os.path.dirname(safe_path)
        os.makedirs(parent, exist_ok=True)

        try:
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "success": True,
                "path": path,
                "size": len(content),
                "absolute_path": safe_path,
            }
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Failed to write file {path}: {str(e)}", details={"path": path})

    async def exec_command(self, mission_id: uuid.UUID, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Deterministic non-executing stub for Phase 2B-4

        Security:
        - No os.system
        - No shell=True
        - No subprocess.run (no host execution)
        - No eval/exec/compile
        - Validates against forbidden patterns
        - Returns deterministic stub result

        Execution Boundary:
        - This is NOT actual container isolation
        - Real Docker container isolation deferred to future phase
        - Returns simulated result with clear documentation
        - Never claims simulated execution is actual isolation
        - Deterministic for tests and CI
        """
        if not command or not isinstance(command, str):
            raise ValidationError("Invalid command: must be non-empty string")

        # Check forbidden patterns
        for pattern in self.FORBIDDEN_COMMAND_PATTERNS:
            if re.search(pattern, command):
                raise ValidationError(
                    f"Forbidden command pattern detected: {pattern}",
                    details={"command": command[:100]},
                )

        # Check forbidden substrings
        for substr in self.FORBIDDEN_SUBSTRINGS:
            if substr in command:
                raise ValidationError(
                    f"Dangerous command rejected: contains {substr}",
                    details={"command": command[:100]},
                )

        # Validate timeout
        if timeout < 1 or timeout > 60:
            raise ValidationError("Timeout must be 1-60 seconds")

        # Ensure workspace exists
        workspace_root = self._get_workspace_root(mission_id)
        os.makedirs(workspace_root, exist_ok=True)

        # Deterministic non-executing stub
        # Does NOT call subprocess.run, does NOT execute on host
        # Returns simulated output based on command for deterministic tests

        # Simple deterministic outputs for common commands for test expectations
        command_lower = command.lower().strip()
        if command_lower.startswith("echo "):
            # Extract echo content
            echo_content = command[5:].strip()
            # Remove quotes if present
            if (echo_content.startswith('"') and echo_content.endswith('"')) or (
                echo_content.startswith("'") and echo_content.endswith("'")
            ):
                echo_content = echo_content[1:-1]
            simulated_output = echo_content
        elif command_lower in ["pwd", "whoami", "date"]:
            simulated_output = f"[Stub] {command} output in workspace {workspace_root}"
        elif command_lower.startswith("ls"):
            # List files in workspace for deterministic stub
            try:
                files = os.listdir(workspace_root)
                simulated_output = "\n".join(files) if files else "(empty)"
            except Exception:
                simulated_output = "(empty)"
        elif command_lower.startswith("cat "):
            # Try to read file via safe path for cat stub
            try:
                cat_path = command[4:].strip()
                safe = self.validate_path(mission_id, cat_path)
                if os.path.exists(safe) and os.path.isfile(safe):
                    with open(safe, "r", encoding="utf-8", errors="ignore") as f:
                        simulated_output = f.read()[:10000]
                else:
                    simulated_output = f"[Stub] File not found: {cat_path}"
            except Exception as e:
                simulated_output = f"[Stub] cat failed: {str(e)[:200]}"
        else:
            simulated_output = f"[Deterministic non-executing stub] Command: {command[:200]}\nWorkspace: {workspace_root}\nNote: Real Docker container isolation deferred to future phase. No host execution performed."

        # Output limit 10KB
        if len(simulated_output) > 10000:
            simulated_output = simulated_output[:10000] + "\n...[truncated]"

        return {
            "success": True,
            "output": simulated_output,
            "exit_code": 0,
            "simulated": True,
            "isolation": "none",
            "execution_boundary": "deterministic non-executing stub - real Docker container isolation deferred",
            "note": "No host execution - stub returns deterministic result for tests. Real isolation requires Docker SDK in future phase.",
        }

    async def cleanup(self, mission_id: uuid.UUID) -> bool:
        """Cleanup workspace"""
        try:
            workspace_root = self._get_workspace_root(mission_id)
            if os.path.exists(workspace_root):
                import shutil
                shutil.rmtree(workspace_root, ignore_errors=True)
            return True
        except Exception:
            return False


class PlaceholderSandboxService(SecureSandboxService):
    """
    Placeholder for backward compatibility - now uses SecureSandboxService
    """

    pass


class ContainerSandboxService(SecureSandboxService):
    """
    Future container isolation implementation placeholder
    Currently uses same secure stub as SecureSandboxService
    Real Docker SDK implementation deferred
    """

    def __init__(self, base_path: Optional[str] = None, runtime: str = "docker"):
        super().__init__(base_path=base_path)
        self.runtime = runtime


# Singleton for app use - can be overridden with Docker implementation in future
sandbox_service = SecureSandboxService()


def get_sandbox_service(service_type: str = "secure") -> SandboxService:
    """
    Factory for SandboxService - compatibility with existing architecture
    Returns SecureSandboxService for all types in Phase 2B-4
    Real container isolation deferred

    Args:
        service_type: Type of service (placeholder, container, secure) - all return SecureSandboxService in Phase 2B-4

    Returns:
        SandboxService instance
    """
    try:
        from app.config import settings
        root = getattr(settings, "sandbox_workspace_root", None)
        if not root:
            root = None
    except Exception:
        root = None

    # For Phase 2B-4, all types return SecureSandboxService with deterministic stub
    # Future: container type would return real Docker-isolated service
    if service_type == "container":
        return ContainerSandboxService(base_path=root)
    else:
        return SecureSandboxService(base_path=root)
