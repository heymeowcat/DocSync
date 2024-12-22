from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter()

@router.get("/download/{lld_path}")
async def download_lld(lld_path: str):
    try:
        lld_path = os.path.join(os.getcwd(), lld_path)
        return FileResponse(lld_path, filename=os.path.basename(lld_path), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="LLD document not found")