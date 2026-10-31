"""One-off crop for Phase 6B portfolio screenshots (not part of app runtime)."""

from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
INCOMING = REPO / "docs" / "screenshots" / "_incoming"
OUT = REPO / "docs" / "screenshots"

# Remove Chrome chrome (~top) and Windows taskbar + dev footer (~bottom).
CHROME_TOP = 142
FOOTER_BOTTOM = 88
MAX_WIDTH = 1280


def crop_app(src: str, dest: str, *, top: int = CHROME_TOP, bottom: int = FOOTER_BOTTOM) -> None:
    im = Image.open(INCOMING / src)
    w, h = im.size
    cropped = im.crop((0, top, w, h - bottom))
    if cropped.width > MAX_WIDTH:
        ratio = MAX_WIDTH / cropped.width
        cropped = cropped.resize(
            (MAX_WIDTH, int(cropped.height * ratio)),
            Image.Resampling.LANCZOS,
        )
    cropped.save(OUT / dest, optimize=True)
    print(dest, cropped.size)


def main() -> None:
    crop_app("6.png", "ask-ai-grounded-answer.png")
    # Keep extra vertical space for expanded source passage text.
    crop_app("13.png", "ask-ai-source-evidence.png", bottom=72)
    crop_app("9.png", "ask-ai-abstention.png")
    crop_app("3.png", "documents-indexed-pdf.png")
    crop_app("7.png", "ask-ai-numeric-fact.png")


if __name__ == "__main__":
    main()
