import logging
import sys
from pathlib import Path
from unittest.mock import Mock


def test_invalid_log_level_warn_and_port_passed(monkeypatch, caplog):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import bridge

    mock_run = Mock()
    monkeypatch.setattr(bridge.uvicorn, "run", mock_run)
    monkeypatch.setenv("BAMBULAB_LOG_LEVEL", "BADLEVEL")
    monkeypatch.setenv("PORT", "1234")

    with caplog.at_level(logging.WARNING):
        bridge.main()

    assert "Invalid log level BADLEVEL provided, falling back to INFO" in caplog.text
    mock_run.assert_called_once_with(bridge.app, host="0.0.0.0", port=1234)
