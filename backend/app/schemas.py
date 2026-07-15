"""Pydantic request/response models.

The public/private response-model split (constitution Article 2 #2) is enforced
here: response schemas expose only fields safe for their audience. Milestone 0
just carries the sandbox shapes; real schemas arrive with their milestones.
"""

from datetime import datetime

from sqlmodel import SQLModel


class SandboxCreate(SQLModel):
    """Request body for ``POST /api/sandbox`` — only client-settable fields."""

    note: str


class SandboxRead(SQLModel):
    """Response model for the sandbox endpoints."""

    id: int
    note: str
    created_at: datetime
