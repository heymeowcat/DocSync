import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from utils import get_directory_tree, load_prompts_from_library

router = APIRouter()


@router.post("/scan_project")
async def scan_project(request: Request):
    """Scan a project directory and return its file tree and prompts."""
    try:
        data = await request.json()
        project_path = data["project_path"]

        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="Directory not found")

        if not os.path.isdir(project_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        tree = {
            "type": "directory",
            "name": os.path.basename(project_path),
            "children": get_directory_tree(project_path),
        }

        prompts = load_prompts_from_library()  # Load the prompts

        return JSONResponse(
            content={  # Return the prompts!
                "tree": tree,
                "prompts": prompts,
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
