from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import tempfile, os
from typing import Any, Dict
from extract_links import clean_agenda
from extract_links import (
    _get_hyperlinks_from_pdf,
    _get_pdf_title_from_source,
    _match_attachments_to_docket_list,
)

app = FastAPI(title="PDF Link Extractor", version="1.0.0")

@app.get("/healthz")
def healthz():
    return {"ok": True}

# /analyze → return all_links
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Empty file upload")
            tmp.write(content)
            tmp_path = tmp.name

        links = _get_hyperlinks_from_pdf(tmp_path)
        all_links = await _get_pdf_title_from_source(links)
        return JSONResponse(content={"all_links": all_links})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

# /analyze-links → return docket_list with matched attachments
@app.post("/analyze-links")
async def analyze_links(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Empty file upload")
            tmp.write(content)
            tmp_path = tmp.name

        docket_list: Dict[str, Any] = clean_agenda(tmp_path)
        links = _get_hyperlinks_from_pdf(tmp_path)
        all_links = await _get_pdf_title_from_source(links)

        final_result = _match_attachments_to_docket_list(docket_list, all_links)
        return JSONResponse(content=final_result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
