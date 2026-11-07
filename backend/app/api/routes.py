import json, uuid, shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from app.services.pdf_service import extract_pdf, render_page_images
from app.services.content_service import build_content_model
from app.ai.qwen_client import analyse_reference
from app.schemas.design import DesignSpec
from app.services.render_service import render_pdf, render_pptx
from app.services.validation_service import validate_output

router=APIRouter(prefix="/api")

def project_dir(pid:str)->Path:
    p=settings.data_dir/pid
    if not p.exists(): raise HTTPException(404,"Project not found")
    return p

@router.post("/projects")
async def create_project(original: UploadFile=File(...), reference: UploadFile=File(...)):
    for f in (original,reference):
        if not f.filename or not f.filename.lower().endswith(".pdf"): raise HTTPException(400,"MVP accepts PDF files only")
    pid=str(uuid.uuid4()); root=settings.data_dir/pid; root.mkdir(parents=True)
    paths=[]
    for name,f in [("original.pdf",original),("reference.pdf",reference)]:
        dest=root/name; data=await f.read()
        if len(data)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"File exceeds upload limit")
        dest.write_bytes(data); paths.append(dest)
    original_data=extract_pdf(paths[0]); reference_data=extract_pdf(paths[1])
    content=build_content_model(original_data)
    (root/"content.json").write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding="utf-8")
    (root/"original-extraction.json").write_text(json.dumps(original_data,ensure_ascii=False,indent=2),encoding="utf-8")
    imgs=render_page_images(paths[1],root/"reference-pages")
    try:
        design=analyse_reference(imgs)
    except Exception as exc:
        # Keep document extraction usable, but make the provider failure visible in the response.
        design=DesignSpec(
            observations=["Reference images were prepared, but AI design analysis failed; starter design tokens are shown for manual review."],
            confidence_notes=[f"AI provider error: {str(exc)[:700]}"]
        )
    (root/"design.json").write_text(design.model_dump_json(indent=2),encoding="utf-8")
    return {"id":pid,"original":{"filename":original.filename,"pages":original_data["page_count"],"text_chars":original_data["text_chars"],"likely_scanned":original_data["likely_scanned"]},
            "reference":{"filename":reference.filename,"pages":reference_data["page_count"]},"content_blocks":len(content["items"]),"design":design.model_dump(),"qwen_enabled":bool(settings.api_key),"ai_warning": design.confidence_notes[0] if design.confidence_notes and "error" in design.confidence_notes[0].lower() else None}

@router.get("/projects/{pid}")
def get_project(pid:str):
    root=project_dir(pid)
    return {"id":pid,"content":json.loads((root/"content.json").read_text()),"design":json.loads((root/"design.json").read_text())}

@router.put("/projects/{pid}/design")
def update_design(pid:str, design:DesignSpec):
    root=project_dir(pid); (root/"design.json").write_text(design.model_dump_json(indent=2),encoding="utf-8")
    return {"saved":True,"design":design.model_dump()}

@router.post("/projects/{pid}/generate")
def generate(pid:str):
    root=project_dir(pid); content=json.loads((root/"content.json").read_text()); design=DesignSpec.model_validate_json((root/"design.json").read_text())
    pdf=root/"redesigned.pdf"; pptx=root/"redesigned.pptx"
    render_pdf(content,design,pdf); render_pptx(content,design,pptx)
    report=validate_output(content["source_text"],str(pdf)); (root/"validation.json").write_text(json.dumps(report,indent=2))
    return {"pdf_url":f"/api/projects/{pid}/download/pdf","pptx_url":f"/api/projects/{pid}/download/pptx","validation":report}

@router.get("/projects/{pid}/download/{kind}")
def download(pid:str,kind:str):
    from fastapi.responses import FileResponse
    if kind not in ("pdf","pptx"): raise HTTPException(400,"Unsupported output")
    path=project_dir(pid)/f"redesigned.{kind}"
    if not path.exists(): raise HTTPException(404,"Generate the document first")
    return FileResponse(path,filename=f"redesigned.{kind}")
