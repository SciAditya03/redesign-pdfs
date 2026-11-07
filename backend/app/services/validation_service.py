import fitz, re

def validate_output(source_text: str, output_pdf: str) -> dict:
    doc=fitz.open(output_pdf); out="\n".join(p.get_text("text", sort=True) for p in doc)
    norm=lambda s: re.sub(r"\s+"," ",s).strip().casefold()
    src=norm(source_text); dst=norm(out)
    # A strict whole-document containment check is conservative; PDF line wrapping is normalised away.
    missing=[]
    for paragraph in [x.strip() for x in source_text.split("\n\n") if len(x.strip()) >= 35]:
        if norm(paragraph) not in dst: missing.append(paragraph[:160])
    return {"output_pages":len(doc),"source_characters":len(source_text),"output_characters":len(out),
            "missing_source_blocks":missing[:100],"passed":len(missing)==0,
            "note":"Text extraction comparison is a useful first check, not a semantic proof of exact preservation."}
