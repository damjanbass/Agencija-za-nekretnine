import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


def _render_pdf_in_thread(html: str) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
            f.write(html)
            tmp_path = Path(f.name)

        try:
            page.goto(tmp_path.as_uri(), wait_until="networkidle")
            pdf_bytes = page.pdf(format="A4", print_background=True, margin={
                "top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"
            })
        finally:
            page.close()
            browser.close()
            tmp_path.unlink(missing_ok=True)

    return pdf_bytes


def generate_pdf(html: str) -> bytes:
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_render_pdf_in_thread, html)
        return future.result()
