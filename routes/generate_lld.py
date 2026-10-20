import json
import os
from xml.etree import ElementTree as ET

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils import generate_lld_from_directory

router = APIRouter()


class GenerateLLDRequest(BaseModel):
    project_path: str
    selected_files: list[str]
    enabled_prompts: dict[str, bool]
    output_format: str = "markdown"


@router.post("/generate_lld")
async def generate_lld(request: GenerateLLDRequest):
    """Generate an LLD document based on the selected files and prompts."""
    print("Received project path:", request.project_path)
    print("Selected files:", request.selected_files)
    print("Enabled prompts:", request.enabled_prompts)
    try:
        # Validate the project path
        if not os.path.exists(request.project_path):
            raise HTTPException(status_code=400, detail="Project path does not exist.")

        # Generate the LLD document using the logic from utils.py
        lld_path, lld_content = generate_lld_from_directory(
            repo_path=request.project_path,
            selected_files=request.selected_files,
            enabled_prompts=request.enabled_prompts,
        )

        if not lld_path or not lld_content:
            raise HTTPException(status_code=500, detail="Failed to generate LLD document.")

        # Save the document based on the selected format
        saved_file_path = save_lld_document(lld_content, request.output_format)

        return {"lld_path": saved_file_path, "markdown_output": lld_content}
    except HTTPException:
        raise  # Re-raise FastAPI HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating LLD: {str(e)}") from e


def save_lld_document(content, output_format):
    """Save the LLD document in the specified format."""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    if output_format == "markdown":
        file_path = os.path.join(output_dir, "lld_document.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    elif output_format == "json":
        file_path = os.path.join(output_dir, "lld_document.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"content": content}, f, indent=2)
    elif output_format == "xml":
        file_path = os.path.join(output_dir, "lld_document.xml")
        root = ET.Element("lld_document")
        ET.SubElement(root, "content").text = content
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)
    elif output_format == "html":
        file_path = os.path.join(output_dir, "lld_document.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"<html><body><pre>{content}</pre></body></html>")
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    return file_path
