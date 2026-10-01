import os
import shutil
import tempfile
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from builder import build_apk

app = FastAPI(title="Web to APK Engine")

def cleanup(folder_path: str):
    shutil.rmtree(folder_path, ignore_errors=True)

@app.get("/")
def home():
    return {"status": "success", "message": "APK Builder Backend is Running Successfully!"}

@app.post("/build")
async def generate_apk(
    background_tasks: BackgroundTasks,
    app_name: str = Form(...),
    package_name: str = Form(...),
    mode: str = Form("url"),  # 'url' অথবা 'html'
    target_url: Optional[str] = Form(None),
    html_code: Optional[str] = Form(None),
    logo: UploadFile = File(...)
):
    try:
        logo_bytes = await logo.read()
        work_dir = tempfile.mkdtemp(prefix="apk_build_")
        
        # APK বিল্ড করা
        apk_path = build_apk(
            work_dir=work_dir,
            app_name=app_name,
            package_name=package_name,
            mode=mode,
            target_url=target_url,
            html_code=html_code,
            logo_bytes=logo_bytes
        )
        
        # ডাউনলোড শেষ হলে ক্যাশ ফোল্ডার ডিলিট করা
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
        raise HTTPException(status_code=500, detail=f"Build Failed: {str(e)}")
