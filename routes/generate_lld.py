from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from utils import generate_lld_from_directory

router = APIRouter()

@router.post("/generate_lld")
async def generate_lld(request: Request):
    try:
        data = await request.json()
        project_path = data["project_path"]
        selected_files = data["selected_files"]
        enabled_prompts = data.get("enabled_prompts", {})
        
        lld_path, markdown_output = generate_lld_from_directory(
            project_path,
            selected_files,
            enabled_prompts
        )
        
        return JSONResponse(content={
            "success": True,
            "lld_path": lld_path,
            "markdown_output": markdown_output
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))