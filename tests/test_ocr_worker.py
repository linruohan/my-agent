from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.ui import ocr_worker


def test_ocr_progress_text():
    assert ocr_worker.ocr_progress_text() == "正在识别中…"


def test_ocr_image_path_in_process_delegates(monkeypatch):
    mock_run = MagicMock(return_value={"ok": True, "text": "hello", "engine": "paddleocr"})
    monkeypatch.setattr(ocr_worker, "run_in_process", mock_run)

    result = ocr_worker.ocr_image_path_in_process("D:/tmp/a.png")
    assert result["ok"]
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] is ocr_worker._ocr_worker
    assert mock_run.call_args.args[1] == str(Path("D:/tmp/a.png"))
    assert mock_run.call_args.kwargs["pool"] == "ocr"
