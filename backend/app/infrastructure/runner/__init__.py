"""Runner-Infrastruktur – Abstraktion für Agent-Kommunikation."""

from app.infrastructure.runner.protocol import RunnerProtocol
from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
from app.infrastructure.runner.wings_adapter import WingsRunnerAdapter

__all__ = ["RunnerProtocol", "StubRunnerAdapter", "WingsRunnerAdapter"]
