"""The committed files in `contract/` match the models."""

from astrolabio_api.contract import export


def test_exported_files_are_up_to_date():
    for name, content in export.render().items():
        path = export.OUTPUT_DIR / name
        assert path.exists(), f"missing {path}; run `uv run export-contract`"
        assert path.read_text(encoding="utf-8") == content, (
            f"{name} is out of date; run `uv run export-contract`"
        )
