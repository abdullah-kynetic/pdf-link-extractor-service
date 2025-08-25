from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import tempfile, os
from typing import Any, Dict
from extract_links import clean_agenda  # make sure this function returns a dict/list

app = FastAPI(title="PDF Link Extractor", version="1.0.0")

@app.get("/healthz")
def healthz():
    return {"ok": True}

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

        # Your script must RETURN a JSON-serializable object (not print)
        result: Dict[str, Any] = clean_agenda(tmp_path)
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except OSError: pass
