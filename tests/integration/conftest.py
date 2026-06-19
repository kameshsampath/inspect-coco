"""Shared fixtures for Docker integration tests."""

from __future__ import annotations

import asyncio
import subprocess

import pytest


def docker_available() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.docker


@pytest.fixture(scope="session")
def check_docker():
    """Skip all Docker tests if Docker is not available."""
    if not docker_available():
        pytest.skip("Docker daemon not available")


@pytest.fixture
async def container(check_docker):
    """Start a temporary Docker container and return an exec function."""
    container_name = "inspect-coco-test"

    # Start container
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "python:3.12-slim",
            "tail",
            "-f",
            "/dev/null",
        ],
        capture_output=True,
        check=True,
    )

    async def exec_fn(
        cmd: list[str],
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ):
        """Execute a command in the test container."""
        docker_cmd = ["docker", "exec"]
        if env:
            for k, v in env.items():
                docker_cmd.extend(["-e", f"{k}={v}"])
        docker_cmd.append(container_name)
        docker_cmd.extend(cmd)

        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        from inspect_coco.config.deployer import ExecResult

        return ExecResult(
            returncode=proc.returncode or 0,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )

    yield exec_fn

    # Cleanup
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
    )
