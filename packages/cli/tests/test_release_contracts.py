from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_container_pins_cjk_font_and_keeps_data_volume_boundary():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG FATHOMARK_NOTO_CJK_VERSION=1:20220127+repack1-1" in dockerfile
    assert "fonts-noto-cjk=${FATHOMARK_NOTO_CJK_VERSION}" in dockerfile
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile
    assert 'VOLUME ["/data"]' in dockerfile
