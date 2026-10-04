from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps import require_role


@pytest.mark.asyncio
async def test_read_only_cannot_use_chat():
    dependency = require_role("USER", "ADMIN")
    with pytest.raises(HTTPException) as error:
        await dependency(SimpleNamespace(role="READ_ONLY"))
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_use_chat():
    dependency = require_role("USER", "ADMIN")
    user = SimpleNamespace(role="ADMIN")
    assert await dependency(user) is user
