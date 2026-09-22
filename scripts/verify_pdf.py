"""Render a report HTML file and verify its browser/PDF release contracts."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from fathomark_reporting.pdf_checks import verify_pdf_structure


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chromium-path", type=Path)
    parser.add_argument(
        "--font-family",
        default="Noto Sans CJK SC",
        help="Font family that must be available to Chromium (default: Noto Sans CJK SC).",
    )
    parser.add_argument(
        "--expected-text",
        action="append",
        default=[],
        help="Text that must be extractable from the generated PDF; repeat as needed.",
    )
    parser.add_argument(
        "--skip-fontconfig",
        action="store_true",
        help="Skip the target-image fc-match check; useful on hosts without fontconfig.",
    )
    return parser


def _verify_fontconfig(font_family: str) -> str:
    fc_match = shutil.which("fc-match")
    if fc_match is None:
        raise RuntimeError("target PDF checks require fontconfig's fc-match command")
    result = subprocess.run(
        [fc_match, "-f", "%{family}", font_family],
        check=True,
        capture_output=True,
        text=True,
    )
    matched = result.stdout.strip()
    if font_family not in matched:
        raise ValueError(
            f"fontconfig resolved {font_family!r} to {matched!r}; pinned font is missing"
        )
    return matched


def verify_html(
    html: str,
    *,
    output_path: Path,
    chromium_path: Path | None,
    font_family: str,
    expected_text: list[str],
    skip_fontconfig: bool = False,
) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PDF browser checks require the optional 'playwright' dependency"
        ) from exc

    system_font_match = None if skip_fontconfig else _verify_fontconfig(font_family)
    widths = (1280, 375)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(chromium_path) if chromium_path else None
        )
        try:
            page = browser.new_page(viewport={"width": widths[0], "height": 900})
            layout = []
            for width in widths:
                page.set_viewport_size({"width": width, "height": 900})
                page.set_content(html, wait_until="load")
                metrics = page.evaluate(
                    """
                    async (fontFamily) => {
                      await document.fonts.ready;
                      const root = document.documentElement;
                      const body = document.body;
                      return {
                        viewport_width: root.clientWidth,
                        document_scroll_width: root.scrollWidth,
                        body_scroll_width: body.scrollWidth,
                        font_status: document.fonts.status,
                        required_font_loaded: document.fonts.check(`12px "${fontFamily}"`),
                        computed_font_family: getComputedStyle(root).fontFamily,
                      };
                    }
                    """,
                    font_family,
                )
                if metrics["document_scroll_width"] > metrics["viewport_width"]:
                    raise ValueError(
                        "HTML overflows the viewport at "
                        f"{width}px: {metrics['document_scroll_width']} > "
                        f"{metrics['viewport_width']}"
                    )
                if (
                    metrics["font_status"] != "loaded"
                    or not metrics["required_font_loaded"]
                ):
                    raise ValueError(
                        f"required font is not loaded at {width}px: {font_family}"
                    )
                layout.append(metrics)

            page.set_viewport_size({"width": widths[0], "height": 900})
            page.set_content(html, wait_until="load")
            page.emulate_media(media="print")
            pdf = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )
        finally:
            browser.close()

    structure = verify_pdf_structure(
        pdf,
        expected_text=expected_text,
        output_path=output_path,
    )
    return {
        "output": str(output_path),
        "fontconfig_match": system_font_match,
        "layout": layout,
        "pdf": {
            "page_count": structure.page_count,
            "text_lengths": structure.text_lengths,
            "fonts_by_page": structure.fonts_by_page,
        },
    }


def main() -> int:
    args = _parser().parse_args()
    result = verify_html(
        args.html.read_text(encoding="utf-8"),
        output_path=args.output,
        chromium_path=args.chromium_path,
        font_family=args.font_family,
        expected_text=args.expected_text,
        skip_fontconfig=args.skip_fontconfig,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
