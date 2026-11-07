import hashlib, re

def build_content_model(extracted: dict) -> dict:
    items=[]
    for page in extracted["pages"]:
        # Paragraph-level IDs remain stable for the same page/text pair; source wording is never sent through a rewrite step.
        paras=[x.strip() for x in re.split(r"\n\s*\n", page["text"]) if x.strip()]
        for idx, text in enumerate(paras):
            digest=hashlib.sha1(f'{page["page_number"]}:{idx}:{text}'.encode()).hexdigest()[:12]
            items.append({"id":f"p{page['page_number']:03d}-b{idx:03d}-{digest}","source_page":page["page_number"],"text":text,"kind":"source_block"})
    return {"source_page_count":extracted["page_count"],"items":items,"source_text":extracted["text"],"locked":True}
