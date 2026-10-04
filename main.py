import os
import shutil
import tempfile
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from builder import build_apk

app = FastAPI(title="Web to APK Engine")

# শুধুমাত্র আপনার নতুন ওয়েবসাইটকে অনুমতি দেওয়া হলো
ALLOWED_ORIGINS = [
    "https://max-apk-bilder-dev-mahin.onrender.com",
    "http://max-apk-bilder-dev-mahin.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def cleanup(folder_path: str):
    shutil.rmtree(folder_path, ignore_errors=True)

@app.get("/")
def home():
    return {"status": "success", "message": "APK Builder Backend is Secured & Running!"}

@app.post("/build")
async def generate_apk(
    request: Request,
    background_tasks: BackgroundTasks,
    app_name: str = Form(...),
    package_name: str = Form(...),
    mode: str = Form("url"),
    target_url: Optional[str] = Form(None),
    html_code: Optional[str] = Form(None),
    logo: UploadFile = File(...)
):
    # ডোমেইন ভেরিফিকেশন
    origin = request.headers.get("origin")
    referer = request.headers.get("referer", "")
    
    is_authorized = (origin in ALLOWED_ORIGINS) or any(referer.startswith(o) for o in ALLOWED_ORIGINS)
    if not is_authorized:
        raise HTTPException(
            status_code=403, 
            detail="Access Denied: আপনার ওয়েবসাইট ছাড়া অন্য কোনো ডোমেইন থেকে এই সার্ভার ব্যবহার করা নিষিদ্ধ!"
        )

    work_dir = tempfile.mkdtemp(prefix="apk_build_")
    try:
        logo_bytes = await logo.read()
        
        apk_path = build_apk(
            work_dir=work_dir,
            app_name=app_name,
            package_name=package_name,
            mode=mode,
            target_url=target_url,
            html_code=html_code,
            logo_bytes=logo_bytes
        )
        
        background_tasks.add_task(cleanup, work_dir)
        
        safe_filename = "".join(c for c in app_name if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_filename = safe_filename.replace(" ", "_") if safe_filename else "app"
        
        return FileResponse(
            apk_path,
            media_type="application/vnd.android.package-archive",
            filename=f"{safe_filename}.apk"
        )
    except Exception as e:
        cleanup(work_dir)
        raise HTTPException(status_code=500, detail=str(e))
