"""Shared fixtures for data-layer tests: real-file excerpts and a fake HTTP session."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
import requests

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class FakeResponse:
    status_code: int
    content: bytes
    headers: dict[str, str] = field(default_factory=dict)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for fake url", response=self)


@dataclass
class FakeSession:
    """Serves canned responses by URL; unknown URLs return 404."""

    routes: dict[str, FakeResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, **_: object) -> FakeResponse:
        self.calls.append(url)
        return self.routes.get(url, FakeResponse(404, b"not found"))


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
