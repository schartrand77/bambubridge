import importlib
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_require_api_key_missing(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    monkeypatch.delenv("BAMBULAB_API_KEY", raising=False)
    import config
    importlib.reload(config)
    import api
    importlib.reload(api)

    with pytest.raises(HTTPException) as excinfo:
        await api.require_api_key("secret")
    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "API key not configured"

