import difflib
from http import client
import os
from os.path import join, dirname
import re
from docx import Document
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, HTTPException, File, UploadFile, BackgroundTasks, logger
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from git import Repo
import uvicorn
import uuid
import shutil
from typing import List
import fnmatch
import mimetypes
import tiktoken
from colorama import init, Fore, Back, Style
import sys
import pyperclip
import xml.etree.ElementTree as ET
import html
import json
from fastapi.middleware.cors import CORSMiddleware

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary directory for storing uploaded files
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# Default ignore patterns
DEFAULT_IGNORE_PATTERNS = [
    '*.pyc', '*.pyo', '*.pyd', '__pycache__',  # Python
    'node_modules', 'bower_components',        # JavaScript
    '.git', '.svn', '.hg', '.gitignore',                    # Version control
    'venv', '.venv', 'env',                    # Virtual environments
    '.idea', '.vscode',                        # IDEs
    '*.log', '*.bak', '*.swp', '*.tmp',        # Temporary and log files
    '.DS_Store',                               # macOS
    'Thumbs.db',                               # Windows
    'build', 'dist',                           # Build directories
    '*.egg-info',                              # Python egg info
    '*.so', '*.dylib', '*.dll'                 # Compiled libraries
]

PROMPT_LIBRARY_DIR = "prompt_library"  # Directory for the prompt library

def get_directory_tree(path: str):
    """
    Recursively builds a directory tree structure.
    """
    tree = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir():
                    tree.append({
                        "type": "directory",
                        "name": entry.name,
                        "children": get_directory_tree(entry.path)
                    })
                elif entry.is_file():
                    tree.append({
                        "type": "file",
                        "name": entry.name,
                        "path": entry.path
                    })
    except Exception as e:
        print(f"Error accessing {path}: {e}")
    return tree

@app.post("/scan_project")
async def scan_project(request: Request):
    try:
        data = await request.json()
        project_path = data["project_path"]
        
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="Directory not found")
            
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        def get_directory_tree(path):
            tree = []
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if entry.is_dir():
                            tree.append({
                                "type": "directory",
                                "name": entry.name,
                                "children": get_directory_tree(entry.path)
                            })
                        elif entry.is_file():
                            tree.append({
                                "type": "file",
                                "name": entry.name,
                                "path": os.path.relpath(entry.path, project_path)
                            })
            except Exception as e:
                print(f"Error accessing {path}: {e}")
            return tree

        tree = {
            "type": "directory",
            "name": os.path.basename(project_path),
            "children": get_directory_tree(project_path)
        }
            
        prompts = load_prompts_from_library()
        
        return JSONResponse(content={
            "tree": tree,
            "prompts": prompts
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@app.post("/generate_paths")
async def generate_paths(selected_files: list[str]):
    """
    Process selected file paths and return a success message.
    """
    try:
        # Simulate processing the selected files (e.g., generate an LLD document)
        print(f"Processing files: {selected_files}")
        return JSONResponse(content={"message": "Paths processed successfully!"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file paths: {str(e)}")

def load_gitignore(path):
    """Loads .gitignore patterns from a given path."""
    gitignore_patterns = []
    gitignore_path = os.path.join(path, '.gitignore')
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r') as f:
            gitignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return gitignore_patterns

def should_ignore(path, base_path, ignore_patterns):
    """Checks if a file or directory should be ignored based on patterns."""
    name = os.path.basename(path)
    rel_path = os.path.relpath(path, base_path)
    abs_path = os.path.abspath(path)

    for pattern in ignore_patterns:
        if fnmatch.fnmatch(name, pattern) or \
           fnmatch.fnmatch(rel_path, pattern) or \
           fnmatch.fnmatch(abs_path, pattern) or \
           (pattern.startswith('/') and fnmatch.fnmatch(abs_path, os.path.join(base_path, pattern[1:]))) or \
           any(fnmatch.fnmatch(part, pattern) for part in rel_path.split(os.sep)):
            return True
    return False

def is_text_file(file_path):
    """Determines if a file is likely a text file based on its content."""
    try:
        with open(file_path, 'rb') as file:
            chunk = file.read(1024)
        return not bool(chunk.translate(None, bytes([7, 8, 9, 10, 12, 13, 27] + list(range(0x20, 0x100)))))
    except IOError:
        return False

def count_tokens(text):
    """Counts the number of tokens in a text string using tiktoken."""
    enc = tiktoken.get_encoding("cl100k_base")
    try:
        return len(enc.encode(text, disallowed_special=()))
    except Exception as e:
        print(f"Warning: Error counting tokens: {str(e)}")
        return 0

def read_file_content(file_path):
    """Reads the content of a file, handling potential encoding errors."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def analyze_directory(path, ignore_patterns, base_path, include_git=False, max_depth=None, current_depth=0):
    """Recursively analyzes a directory and its contents."""
    if max_depth is not None and current_depth > max_depth:
        return None

    result = {
        "name": os.path.basename(path),
        "type": "directory",
        "size": 0,
        "children": [],
        "total_tokens": 0,
        "file_count": 0,
        "dir_count": 0,
        "text_content_size": 0,
        "total_text_size": 0,  # New field for total size of all text files
        "path": path  # Add path to the result
    }

    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            
            # Skip .git directory unless explicitly included
            if item == '.git' and not include_git:
                continue

            is_ignored = should_ignore(item_path, base_path, ignore_patterns)

            if os.path.isfile(item_path) and is_text_file(item_path):
                file_size = os.path.getsize(item_path)
                result["total_text_size"] += file_size

            if is_ignored:
                continue  # Skip ignored items for further analysis

            if os.path.isfile(item_path):
                file_size = os.path.getsize(item_path)
                is_text = is_text_file(item_path)
                if is_text:
                    content = read_file_content(item_path)
                    tokens = count_tokens(content)
                else:
                    content = "[Non-text file]"
                    tokens = 0
                child = {
                    "name": item,
                    "type": "file",
                    "size": file_size,
                    "tokens": tokens,
                    "content": content,
                    "is_ignored": is_ignored,
                    "path": item_path
                }
                result["children"].append(child)
                if not is_ignored:
                    result["size"] += file_size
                    result["total_tokens"] += tokens
                    result["file_count"] += 1
                    if is_text:
                        result["text_content_size"] += len(content)
            elif os.path.isdir(item_path):
                subdir = analyze_directory(item_path, ignore_patterns, base_path, include_git, max_depth, current_depth + 1)
                if subdir:
                    subdir["is_ignored"] = is_ignored
                    result["children"].append(subdir)
                    if not is_ignored:
                        result["size"] += subdir["size"]
                        result["total_tokens"] += subdir["total_tokens"]
                        result["file_count"] += subdir["file_count"]
                        result["dir_count"] += 1 + subdir["dir_count"]
                        result["text_content_size"] += subdir["text_content_size"]
    except PermissionError:
        print(Fore.RED + f"Permission denied: {path}" + Style.RESET_ALL)

    return result

def generate_tree_string(node, prefix="", is_last=True, show_size=False, show_ignored=False, use_color=False):
    """Generates a string representation of the directory tree."""
    if node.get("is_ignored", False) and not show_ignored:
        return ""

    if use_color:
        result = prefix + (Fore.GREEN + "└── " if is_last else "├── ")
        result += Fore.BLUE + node["name"] + Style.RESET_ALL
    else:
        result = prefix + ("└── " if is_last else "├── ") + node["name"]

    if show_size and node["type"] == "file":
        size_str = f" ({node['size']} bytes)"
        result += Fore.YELLOW + size_str + Style.RESET_ALL if use_color else size_str

    if node.get("is_ignored", False):
        ignored_str = " [IGNORED]"
        result += Fore.RED + ignored_str + Style.RESET_ALL if use_color else ignored_str

    result += "\n"

    if node["type"] == "directory":
        prefix += "    " if is_last else "│   "
        children = node["children"]
        if not show_ignored:
            children = [child for child in children if not child.get("is_ignored", False)]
        for i, child in enumerate(children):
            result += generate_tree_string(child, prefix, i == len(children) - 1, show_size, show_ignored, use_color)
    return result

def generate_summary_string(data, estimated_size, use_color=True):
    summary = "\nSummary:\n"
    summary += f"Total files analyzed: {data['file_count']}\n"
    summary += f"Total directories analyzed: {data['dir_count']}\n"
    summary += f"Estimated output size: {estimated_size / 1024:.2f} KB\n"
    summary += f"Actual analyzed size: {data['size'] / 1024:.2f} KB\n"
    summary += f"Total tokens: {data['total_tokens']}\n"
    summary += f"Actual text content size: {data['text_content_size'] / 1024:.2f} KB\n"
    
    if use_color:
        return Fore.CYAN + summary + Style.RESET_ALL
    return summary

def generate_content_string(data):
    """Generates a structured representation of file contents."""
    content = []

    def add_file_content(node, path=""):
        if node["type"] == "file" and not node.get("is_ignored", False) and node["content"] != "[Non-text file]":
            content.append({
                "path": os.path.join(path, node["name"]),
                "content": node["content"]
            })
        elif node["type"] == "directory":
            for child in node["children"]:
                add_file_content(child, os.path.join(path, node["name"]))

    add_file_content(data)
    return content

def generate_markdown_output(data):
    output = f"# Codebase Analysis for: {data['name']}\n\n"
    output += "## Directory Structure\n\n"
    output += "```\n"
    output += generate_tree_string(data, show_size=True, show_ignored=True)
    output += "```\n\n"
    output += "## Summary\n\n"
    output += f"- Total files: {data['file_count']}\n"
    output += f"- Total directories: {data['dir_count']}\n"
    output += f"- Analyzed size: {data['size'] / 1024:.2f} KB\n"
    output += f"- Total text file size (including ignored): {data['total_text_size'] / 1024:.2f} KB\n"
    output += f"- Total tokens: {data['total_tokens']}\n"
    output += f"- Analyzed text content size: {data['text_content_size'] / 1024:.2f} KB\n\n"
    output += "## File Contents\n\n"
    for file in generate_content_string(data):
        output += f"### {file['path']}\n\n```\n{file['content']}\n```\n\n"
    return output

def generate_xml_output(data):
    root = ET.Element("codebase-analysis")
    ET.SubElement(root, "name").text = data['name']
    structure = ET.SubElement(root, "directory-structure")
    structure.text = generate_tree_string(data, show_size=True, show_ignored=True)
    summary = ET.SubElement(root, "summary")
    ET.SubElement(summary, "total-files").text = str(data['file_count'])
    ET.SubElement(summary, "total-directories").text = str(data['dir_count'])
    ET.SubElement(summary, "analyzed-size-kb").text = f"{data['size'] / 1024:.2f}"
    ET.SubElement(summary, "total-text-file-size-kb").text = f"{data['total_text_size'] / 1024:.2f}"
    ET.SubElement(summary, "total-tokens").text = str(data['total_tokens'])
    ET.SubElement(summary, "analyzed-text-content-size-kb").text = f"{data['text_content_size'] / 1024:.2f}"
    contents = ET.SubElement(root, "file-contents")
    for file in generate_content_string(data):
        file_elem = ET.SubElement(contents, "file")
        ET.SubElement(file_elem, "path").text = file['path']
        ET.SubElement(file_elem, "content").text = file['content']
    return ET.tostring(root, encoding="unicode")

def generate_html_output(data):
    output = f"""
    <html>
    <head>
        <title>Codebase Analysis for: {html.escape(data['name'])}</title>
        <style>
            pre {{ white-space: pre-wrap; word-wrap: break-word; }}
        </style>
    </head>
    <body>
    <h1>Codebase Analysis for: {html.escape(data['name'])}</h1>
    <h2>Directory Structure</h2>
    <pre>{html.escape(generate_tree_string(data, show_size=True, show_ignored=True))}</pre>
    <h2>Summary</h2>
    <ul>
    <li>Total files: {data['file_count']}</li>
    <li>Total directories: {data['dir_count']}</li>
    <li>Analyzed size: {data['size'] / 1024:.2f} KB</li>
    <li>Total text file size (including ignored): {data['total_text_size'] / 1024:.2f} KB</li>
    <li>Total tokens: {data['total_tokens']}</li>
    <li>Analyzed text content size: {data['text_content_size'] / 1024:.2f} KB</li>
    </ul>
    <h2>File Contents</h2>
    """
    for file in generate_content_string(data):
        output += f"<h3>{html.escape(file['path'])}</h3><pre>{html.escape(file['content'])}</pre>"
    output += "</body></html>"
    return output

def load_ignore_patterns(base_path):
    patterns = set(DEFAULT_IGNORE_PATTERNS)

    # Load patterns from .cdigestignore file if it exists
    cdigestignore_path = os.path.join(base_path, '.cdigestignore')
    if os.path.exists(cdigestignore_path):
        with open(cdigestignore_path, 'r') as f:
            file_patterns = {line.strip() for line in f if line.strip() and not line.startswith('#')}
        patterns.update(file_patterns)

    # Load patterns from .gitignore file if it exists
    gitignore_path = os.path.join(base_path, '.gitignore')
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r') as f:
            file_patterns = {line.strip() for line in f if line.strip() and not line.startswith('#')}
        patterns.update(file_patterns)

    print(f"Debug: Final ignore patterns: {patterns}")
    return patterns

def estimate_output_size(path, ignore_patterns, base_path):
    estimated_size = 0
    file_count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), base_path, ignore_patterns)]
        for file in files:
            file_path = os.path.join(root, file)
            if not should_ignore(file_path, base_path, ignore_patterns) and is_text_file(file_path):
                file_size = os.path.getsize(file_path)
                estimated_size += file_size
                file_count += 1
    
    # Add some overhead for the directory structure and summary
    estimated_size += file_count * 100  # Assume 100 bytes per file for structure
    estimated_size += 1000  # Add 1KB for summary

    return estimated_size

def generate_folder_structure_from_upload(repo_path, ignore_patterns):
    """Generates a nested dictionary representing the folder structure, handling ignore patterns."""
    structure = {"name": os.path.basename(repo_path), "type": "directory", "children": []}

    for root, dirs, files in os.walk(repo_path):
        # Apply ignore patterns to directories
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), repo_path, ignore_patterns)]

        current_level = structure
        rel_path = os.path.relpath(root, repo_path)
        if rel_path != ".":
            path_parts = rel_path.split(os.sep)
            for part in path_parts:
                for child in current_level["children"]:
                    if child["name"] == part and child["type"] == "directory":
                        current_level = child
                        break

        for file in files:
            if not should_ignore(os.path.join(root, file), repo_path, ignore_patterns):
                current_level["children"].append({"name": file, "type": "file", "path": os.path.join(rel_path, file)})

        for dir_name in dirs:
            current_level["children"].append({"name": dir_name, "type": "directory", "children": []})

    return structure

def generate_tldr(file_content, file_path):
    prompt = f"""Summarize the content of the following file:
    File Path: {file_path}
    File Content: {file_content}
    """
    
    response = client.chat.completions.create(
        model="meta-llama/llama-3.2-3b-instruct:free",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content

def generate_lld_section(prompt):
    response = client.chat.completions.create(
        model="meta-llama/llama-3.2-3b-instruct:free",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    raw_text = response.choices[0].message.content
    filtered_text = re.sub(r'<.*?>', '', raw_text).strip()
    return filtered_text

def generate_detailed_commit_info(repo_path, old_commit, new_commit, lld_path=None):
    repo = Repo(repo_path)
    
    # Get commits
    old_commit_obj = repo.commit(old_commit)
    new_commit_obj = repo.commit(new_commit)
    
    # Detailed commit entries
    detailed_entries = []
    
    # Commits between old and new
    commits = list(repo.iter_commits(f"{old_commit}..{new_commit}"))
    
    for commit in commits:
        entry = {
            'commit_hash': str(commit),
            'message': commit.message,
            'author': commit.author.name,
            'email': commit.author.email,
            'date': commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Collect file changes
        file_changes = []
        diffs = []
        
        for d in commit.diff(commit.parents[0] if commit.parents else None):
            change_type = {
                'A': 'Added',
                'D': 'Deleted',
                'M': 'Modified',
                'R': 'Renamed'
            }.get(d.change_type, 'Unknown')
            
            file_change = {
                'file': d.a_path,
                'change_type': change_type
            }
            file_changes.append(file_change)
            
            # Get diff content for modified files
            if change_type == 'Modified':
                try:
                    blob_old = old_commit_obj.tree[d.a_path]
                    blob_new = new_commit_obj.tree[d.a_path]
                    
                    old_content = blob_old.data_stream.read().decode('utf-8', errors='ignore')
                    new_content = blob_new.data_stream.read().decode('utf-8', errors='ignore')
                    
                    diff_lines = list(difflib.unified_diff(
                        old_content.splitlines(), 
                        new_content.splitlines(), 
                        fromfile=f'a/{d.a_path}', 
                        tofile=f'b/{d.a_path}'
                    ))
                    
                    # Generate TLDR for this specific change
                    tldr_section = generate_tldr(new_content, d.a_path)
                    
                    diffs.append({
                        'file': d.a_path,
                        'diff_content': diff_lines,
                        'tldr_section': tldr_section
                    })
                except KeyError as e:
                    logger.warning(f"File {d.a_path} not found in commit {commit.hexsha}: {e}")
                except Exception as e:
                    logger.error(f"Error processing {d.a_path}: {e}")
        
        entry['file_changes'] = file_changes
        entry['diffs'] = diffs
        detailed_entries.append(entry)
    
    combined_tldrs = "\n\n".join([diff['tldr_section'] for entry in detailed_entries for diff in entry.get('diffs', [])])
    
    lld_sections = {}
    lld_sections['introduction'] = generate_lld_section(f"Generate an introduction for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['system_overview'] = generate_lld_section(f"Generate a system overview for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['detailed_design'] = generate_lld_section(f"Generate a detailed design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['data_design'] = generate_lld_section(f"Generate a data design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['interface_design'] = generate_lld_section(f"Generate an interface design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['algorithm_design'] = generate_lld_section(f"Generate an algorithm design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['security_design'] = generate_lld_section(f"Generate a security design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['error_handling_and_logging'] = generate_lld_section(f"Generate an error handling and logging section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['performance_considerations'] = generate_lld_section(f"Generate a performance considerations section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['testing_and_validation'] = generate_lld_section(f"Generate a testing and validation section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['deployment_considerations'] = generate_lld_section(f"Generate a deployment considerations section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['assumptions_and_dependencies'] = generate_lld_section(f"Generate an assumptions and dependencies section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    lld_sections['appendix'] = generate_lld_section(f"Generate an appendix section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    
    # Create LLD document
    if not lld_path:
        lld_path = os.path.join(repo_path, 'project_lld.docx')
    
    doc = Document()
    doc.add_heading('Low-Level Design (LLD) Document', 0)
    
    # Add generated sections to the document
    doc.add_heading('1. Introduction', level=1)
    doc.add_paragraph(lld_sections['introduction'])
    
    doc.add_heading('2. System Overview', level=1)
    doc.add_paragraph(lld_sections['system_overview'])
    
    doc.add_heading('3. Detailed Design', level=1)
    doc.add_paragraph(lld_sections['detailed_design'])
    
    doc.add_heading('4. Data Design', level=1)
    doc.add_paragraph(lld_sections['data_design'])
    
    doc.add_heading('5. Interface Design', level=1)
    doc.add_paragraph(lld_sections['interface_design'])
    
    doc.add_heading('6. Algorithm Design', level=1)
    doc.add_paragraph(lld_sections['algorithm_design'])
    
    doc.add_heading('7. Security Design', level=1)
    doc.add_paragraph(lld_sections['security_design'])
    
    doc.add_heading('8. Error Handling and Logging', level=1)
    doc.add_paragraph(lld_sections['error_handling_and_logging'])
    
    doc.add_heading('9. Performance Considerations', level=1)
    doc.add_paragraph(lld_sections['performance_considerations'])
    
    doc.add_heading('10. Testing and Validation', level=1)
    doc.add_paragraph(lld_sections['testing_and_validation'])
    
    doc.add_heading('11. Deployment Considerations', level=1)
    doc.add_paragraph(lld_sections['deployment_considerations'])
    
    doc.add_heading('12. Assumptions and Dependencies', level=1)
    doc.add_paragraph(lld_sections['assumptions_and_dependencies'])
    
    doc.add_heading('13. Appendix', level=1)
    doc.add_paragraph(lld_sections['appendix'])
    
    doc.save(lld_path)
    
    return {
        'detailed_entries': detailed_entries,
        'lld_path': lld_path
    }

def load_prompts_from_library():
    """Loads prompts from the prompt library directory."""
    prompts = {}
    if not os.path.exists(PROMPT_LIBRARY_DIR):
        return prompts
    
    for filename in os.listdir(PROMPT_LIBRARY_DIR):
        if filename.endswith(".md"):
            filepath = os.path.join(PROMPT_LIBRARY_DIR, filename)
            with open(filepath, "r") as f:
                content = f.read()
                # Use the filename as the key and content as the value
                prompts[filename] = content
    return prompts

def format_prompt_name(filename):
    """Formats the prompt name for display."""
    name = filename[:-3]  # Remove .md extension
    name = name.replace("_", " ").title()  # Replace underscores and capitalize
    return name

def generate_lld_from_directory(repo_path, selected_files, enabled_prompts, lld_path=None):
    """
    Generate LLD document from selected files in the directory
    """
    summaries = {}
    for file_path in selected_files:
        full_path = os.path.join(repo_path, file_path)
        if os.path.isfile(full_path):
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            summary = generate_tldr(content, file_path)
            summaries[file_path] = summary
    
    combined_tldrs = "\n\n".join(summaries.values())
    project_summary = generate_lld_section(f"Summarize the entire project based on these file summaries:\n{combined_tldrs}")
    
    # Generate sections based on enabled prompts
    lld_sections = {}
    for prompt_name, is_enabled in enabled_prompts.items():
        if is_enabled:
            prompt_content = load_prompt_content(prompt_name)
            if prompt_content:
                section_name = format_prompt_name(prompt_name)
                lld_sections[section_name] = generate_lld_section(
                    f"{prompt_content}\n{project_summary}"
                )
    
    # Create and save the document
    if not lld_path:
        lld_path = os.path.join(repo_path, 'project_lld.docx')
        
    doc = Document()
    doc.add_heading('Low-Level Design (LLD) Document', 0)
    
    for section_name, content in lld_sections.items():
        doc.add_heading(section_name, level=1)
        doc.add_paragraph(content)
    
    doc.save(lld_path)
    
    # Generate markdown output for preview
    markdown_output = generate_markdown_output(
        analyze_directory(repo_path, load_ignore_patterns(repo_path), repo_path)
    )
    
    return lld_path, markdown_output

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    prompts = load_prompts_from_library()
    formatted_prompts = {format_prompt_name(filename): content for filename, content in prompts.items()}
    return templates.TemplateResponse("index.html", {
        "request": request,
        "result": None,
        "summary": "",
        "tree": None,
        "content": "",
        "prompts": formatted_prompts
    })

@app.post("/upload_project")
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
        logger.error(f"Error processing uploaded project: {e}")
        return JSONResponse(content={"error": f"Error processing project: {e}"}, status_code=500)




@app.post("/generate_lld")
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

@app.get("/download/{lld_path}")
async def download_lld(lld_path: str):
    try:
        lld_path = os.path.join(os.getcwd(), lld_path)
        return FileResponse(lld_path, filename=os.path.basename(lld_path), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="LLD document not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)