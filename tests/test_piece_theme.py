import base64

from src import asset_loader


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+7lP6NwAAAABJRU5ErkJggg=="
)


class _Response:
    content = _PNG

    def raise_for_status(self):
        return None


def test_uses_the_official_neo_piece_urls():
    assert asset_loader.PIECE_THEME == "neo"
    assert asset_loader.piece_url("w", "Q") == (
        "https://www.chess.com/chess-themes/pieces/neo/300/wq.png"
    )
    assert asset_loader.piece_url("b", "N").endswith("/bn.png")


def test_downloads_and_marks_the_complete_neo_set(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return _Response()

    monkeypatch.setattr(asset_loader.requests, "get", fake_get)

    assert asset_loader.download_pieces(tmp_path)
    assert len(calls) == 12
    assert all("/pieces/neo/300/" in url for url, _ in calls)
    assert (tmp_path / ".piece-theme").read_text() == "neo"
    assert (tmp_path / "wQ.png").read_bytes() == _PNG
