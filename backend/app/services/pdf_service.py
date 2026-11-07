import fitz, re, hashlib
from pathlib import Path

def extract_pdf(path: Path) -> dict:
    doc = fitz.open(path)
    pages, all_text = [], []
    for i, page in enumerate(doc):
        text = page.get_text("text", sort=True)
        blocks = page.get_text("blocks")
        pages.append({"page_number": i + 1, "text": text, "blocks": len(blocks), "width": round(page.rect.width, 2), "height": round(page.rect.height, 2)})
        all_text.append(text)
    full = "\n".join(all_text)
    normalized = re.sub(r"\s+", " ", full).strip()
    return {"page_count": len(doc), "pages": pages, "text": full, "normalized_text": normalized,
            "text_chars": len(full), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "likely_scanned": sum(len(p["text"].strip()) for p in pages) < 80 * max(1, len(pages))}

def render_page_images(path: Path, out_dir: Path, limit: int = 6) -> list[Path]:
    doc = fitz.open(path); out_dir.mkdir(parents=True, exist_ok=True); paths=[]
    for i, page in enumerate(doc):
        if i >= limit: break
        pix = page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
        p = out_dir / f"reference-page-{i+1}.jpg"; pix.save(p); paths.append(p)
    return paths
