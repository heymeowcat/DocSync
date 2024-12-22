from fastapi import APIRouter, Request, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from utils import format_prompt_name, generate_folder_structure_from_upload, load_ignore_patterns, load_prompts_from_library
import os
import uuid
import shutil

router = APIRouter()

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

@router.post("/upload_project")
async def upload_project(request: Request, background_tasks: BackgroundTasks, project_path: UploadFile = File(...)):
    try:
        temp_dir = os.path.join(TEMP_DIR, str(uuid.uuid4()))
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, project_path.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(project_path.file, buffer)

        ignore_patterns = load_ignore_patterns(temp_dir)
        folder_structure = generate_folder_structure_from_upload(temp_dir, ignore_patterns)

        prompts = load_prompts_from_library()
        formatted_prompts = {format_prompt_name(filename): content for filename, content in prompts.items()}

        def cleanup_temp_dir():
            shutil.rmtree(temp_dir)

        background_tasks.add_task(cleanup_temp_dir)

        return JSONResponse(content={
            "tree": folder_structure,
            "prompts": formatted_prompts,
            "temp_dir_id": os.path.basename(temp_dir)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))