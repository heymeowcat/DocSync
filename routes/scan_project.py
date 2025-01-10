from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

router = APIRouter()

class ScanProjectRequest(BaseModel):
    project_path: str

@router.post("/scan_project")
async def scan_project(request: ScanProjectRequest):
    """Scan a project directory and return its file tree."""
    try:
        if not os.path.exists(request.project_path):
            raise HTTPException(status_code=400, detail="Project path does not exist.")

        file_tree = build_file_tree(request.project_path)
        return {"tree": file_tree, "prompts": {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scanning project: {str(e)}")

def build_file_tree(path):
    """Build a file tree structure from a directory."""
    if not os.path.isdir(path):
        return None

    file_tree = {"type": "directory", "name": os.path.basename(path), "path": path, "children": []}

    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            file_tree["children"].append(build_file_tree(item_path))
        elif os.path.isfile(item_path):
            file_tree["children"].append({
                "type": "file",
                "name": item,
                "path": item_path
            })

    return file_tree