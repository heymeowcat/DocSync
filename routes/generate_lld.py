from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from utils import generate_lld_from_directory, generate_mermaid_diagram

router = APIRouter()

@router.post("/generate_lld")
async def generate_lld(request: Request):
    try:
        data = await request.json()
        project_path = data["project_path"]
        selected_files = data["selected_files"]
        enabled_prompts = data.get("enabled_prompts", {})
        
        # Debug log
        print(f"Project Path: {project_path}")
        print(f"Selected Files: {selected_files}")
        print(f"Enabled Prompts: {enabled_prompts}")
        
        lld_path, markdown_output = generate_lld_from_directory(
            project_path,
            selected_files,
            enabled_prompts
        )
        
       
        mermaid_diagrams = []
        for section in markdown_output.split("\n\n"):
            if "```mermaid" in section:
                mermaid_diagrams.append(section)
        
        return JSONResponse(content={
            "success": True,
            "lld_path": lld_path,
            "markdown_output": markdown_output,
            "mermaid_diagrams": mermaid_diagrams
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))