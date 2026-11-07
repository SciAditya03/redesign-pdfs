from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from app.schemas.design import DesignSpec

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "renderer" / "templates"

def render_pdf(content: dict, design: DesignSpec, output: Path, title: str = "Redesigned document"):
    env=Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    html=env.get_template("document.html").render(content=content, design=design, title=title)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=str(output), format=design.tokens.page_size, print_background=True,
                 margin={"top":"18mm","right":"17mm","bottom":"18mm","left":"17mm"}, prefer_css_page_size=True)
        browser.close()

def render_pptx(content: dict, design: DesignSpec, output: Path, title: str = "Redesigned document"):
    prs=Presentation(); prs.slide_width= Inches(8.27); prs.slide_height= Inches(11.69)
    blank=prs.slide_layouts[6]
    blocks=content.get("items",[])
    chunks=[]
    for block in blocks:
        txt=block["text"].strip()
        if txt: chunks.append((block["source_page"],txt))
    # Editable, source-faithful text flow. Each source page becomes a slide; later layout templates can map semantic blocks.
    grouped={}
    for pg,txt in chunks: grouped.setdefault(pg,[]).append(txt)
    for page_no, texts in grouped.items():
        slide=prs.slides.add_slide(blank)
        bg=slide.background.fill; bg.solid(); bg.fore_color.rgb=RGBColor.from_string(design.tokens.background_color.lstrip("#"))
        head=slide.shapes.add_textbox(Inches(.65), Inches(.35), Inches(6.9), Inches(.45)).text_frame
        head.text=title; head.paragraphs[0].font.size=Pt(9); head.paragraphs[0].font.bold=True
        box=slide.shapes.add_textbox(Inches(.65), Inches(1.0), Inches(6.9), Inches(9.9)).text_frame
        box.word_wrap=True
        first=True
        for text in texts:
            p=box.paragraphs[0] if first else box.add_paragraph(); first=False
            p.text=text; p.font.size=Pt(10); p.space_after=Pt(8)
        foot=slide.shapes.add_textbox(Inches(.65), Inches(11.15), Inches(6.9), Inches(.2)).text_frame
        foot.text=f"{title.upper()}   •   SOURCE PAGE {page_no}"
        foot.paragraphs[0].font.size=Pt(7)
    prs.save(output)
