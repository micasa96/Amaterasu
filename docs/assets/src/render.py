"""Render the README banner and GitHub social preview from banner.html.

The page uses the dark-side tokens of web/ui/src/styles/tokens.css and the
Mona Sans file from web/ui/node_modules, so run `npm ci` in web/ui first.

    python docs/assets/src/render.py      (needs: pip install playwright; playwright install chromium)

Writes docs/assets/blackflare-github-banner.png (3200x1200, transparent
rounded corners) and docs/assets/blackflare-social-preview.png (1280x640).
Upload the social preview in GitHub: Settings > General > Social preview.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
JOBS = [  # name, width, height, scale, transparent corners, output file
    ("banner", 1600, 600, 2, True, "blackflare-github-banner.png"),
    ("social", 1280, 640, 1, False, "blackflare-social-preview.png"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--allow-file-access-from-files"])
    for name, w, h, scale, transparent, out in JOBS:
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        page.goto((HERE / "banner.html").as_uri() + "#" + name)
        page.evaluate("document.fonts.ready")
        if not page.evaluate("document.fonts.check('500 40px \"Mona Sans Variable\"')"):
            raise SystemExit("Mona Sans did not load: run `npm ci` in web/ui first.")
        page.locator(".frame").screenshot(path=str(OUT / out), omit_background=transparent)
        print("wrote", out)
        page.close()
    browser.close()
