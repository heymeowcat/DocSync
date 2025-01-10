from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json
from xml.etree import ElementTree as ET

router = APIRouter()

class GenerateLLDRequest(BaseModel):
    project_path: str
    selected_files: list[str]
    enabled_prompts: dict[str, bool]
    output_format: str = "markdown" 

@router.post("/generate_lld")
async def generate_lld(request: GenerateLLDRequest):
    """Generate an LLD document based on the selected files and prompts."""
    try:
        # Generate the LLD document (replace with your logic)
        lld_content = generate_lld_content(request.project_path, request.selected_files, request.enabled_prompts)

        # Save the document based on the selected format
        lld_path = save_lld_document(lld_content, request.output_format)

        return {"lld_path": lld_path, "markdown_output": lld_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating LLD: {str(e)}")

def generate_lld_content(project_path, selected_files, enabled_prompts):
    """Generate LLD content based on the selected files and prompts."""
    # Replace with your logic to generate LLD content
    return f"# LLD Document\n\nGenerated for {project_path} with {len(selected_files)} files."

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