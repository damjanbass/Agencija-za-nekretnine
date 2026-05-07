from weasyprint import HTML


def generate_pdf(html: str) -> bytes:
    return HTML(string=html, base_url=None).write_pdf()
