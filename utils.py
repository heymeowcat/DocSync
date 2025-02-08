import base64
from io import BytesIO
import os
from docx import Document
from openai import OpenAI
import re
import requests
import tiktoken
import fnmatch
from colorama import Fore, Style
from dotenv import load_dotenv
from os.path import join, dirname
from docx.shared import Inches
import markdown
import pypandoc

# Load environment variables
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Initialize OpenAI client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

# Default ignore patterns
DEFAULT_IGNORE_PATTERNS = [
    '*.pyc', '*.pyo', '*.pyd', '__pycache__',  # Python
    'node_modules', 'bower_components',        # JavaScript
    '.git', '.svn', '.hg', '.gitignore',       # Version control
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

def markdown_to_docx(markdown_content, output_path):
    """Convert markdown content to DOCX using pandoc."""
    try:
        # Convert markdown to docx using pandoc
        pypandoc.convert_text(
            markdown_content,
            'docx',
            outputfile=output_path,
            format='md',
            extra_args=['--standalone', '--wrap=none']
        )
        return True
    except Exception as e:
        print(f"Error converting markdown to docx: {e}")
        return False

# Helper function to format prompt names
def format_prompt_name(filename):
    """Formats the prompt name for display."""
    name = filename[:-3]  # Remove .md extension
    name = name.replace("_", " ").title()  # Replace underscores and capitalize
    return name

def get_directory_tree(path: str):
    """Recursively builds a directory tree structure."""
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

# Load prompts from the prompt library
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
                prompts[filename] = content
    return prompts

def generate_folder_structure_from_upload(repo_path, ignore_patterns):
    """Generates a nested dictionary representing the folder structure."""
    structure = {"name": os.path.basename(repo_path), "type": "directory", "children": []}
    
    for root, dirs, files in os.walk(repo_path):
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
                current_level["children"].append({
                    "name": file, 
                    "type": "file", 
                    "path": os.path.join(rel_path, file)
                })
        
        for dir_name in dirs:
            current_level["children"].append({
                "name": dir_name, 
                "type": "directory", 
                "children": []
            })
    
    return structure

def generate_tldr(file_content, file_path):
    """Generate a TLDR summary for a file."""
    prompt = f"""Summarize the content of the following file:
    File Path: {file_path}
    File Content: {file_content}
    """
    
    response = client.chat.completions.create(
        model="meta-llama/llama-3.2-3b-instruct:free",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content

def generate_lld_section(prompt):
    """Generate an LLD section based on a prompt."""
    response = client.chat.completions.create(
        model="meta-llama/llama-3.2-3b-instruct:free",
        messages=[{"role": "user", "content": prompt}]
    )
    
    raw_text = response.choices[0].message.content
    filtered_text = re.sub(r'<.*?>', '', raw_text).strip()
    return filtered_text

def analyze_directory(path, ignore_patterns, base_path, include_git=False, max_depth=None, current_depth=0):
    """Recursively analyze a directory and its contents."""
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
        "total_text_size": 0,
        "path": path
    }

    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            
            if item == '.git' and not include_git:
                continue

            is_ignored = should_ignore(item_path, base_path, ignore_patterns)

            if os.path.isfile(item_path) and is_text_file(item_path):
                file_size = os.path.getsize(item_path)
                result["total_text_size"] += file_size

            if is_ignored:
                continue

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
        print(f"Permission denied: {path}")

    return result

def load_ignore_patterns(base_path):
    """Load ignore patterns from default and custom ignore files."""
    patterns = set(DEFAULT_IGNORE_PATTERNS)

    for ignore_file in ['.cdigestignore', '.gitignore']:
        ignore_path = os.path.join(base_path, ignore_file)
        if os.path.exists(ignore_path):
            with open(ignore_path, 'r') as f:
                patterns.update(line.strip() for line in f if line.strip() and not line.startswith('#'))

    return patterns

def should_ignore(path, base_path, ignore_patterns):
    """Check if a file or directory should be ignored."""
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
    """Check if a file is a text file."""
    try:
        with open(file_path, 'rb') as file:
            chunk = file.read(1024)
        return not bool(chunk.translate(None, bytes([7, 8, 9, 10, 12, 13, 27] + list(range(0x20, 0x100)))))
    except IOError:
        return False

def read_file_content(file_path):
    """Read file content safely."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def count_tokens(text):
    """Count tokens in text using tiktoken."""
    enc = tiktoken.get_encoding("cl100k_base")
    try:
        return len(enc.encode(text, disallowed_special=()))
    except Exception as e:
        print(f"Warning: Error counting tokens: {str(e)}")
        return 0

def generate_lld_from_directory(repo_path, selected_files, enabled_prompts, lld_path=None):
    """Generate LLD document from selected files."""

    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Repository path {repo_path} does not exist")
    if not selected_files:
        raise ValueError("No files selected for analysis")

    summaries = {}
    for file_path in selected_files:
        full_path = '/' + file_path if not file_path.startswith('/') else file_path
        
        print(f"[DEBUG] Processing file: {full_path}")
        if os.path.isfile(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if not content.strip():
                    print(f"[WARN] File {file_path} is empty or unreadable.")
                    continue
                summary = generate_tldr(content, file_path) # Assuming this function is defined
                if not summary:
                    print(f"[WARN] No summary generated for {file_path}.")
                    continue
                summaries[file_path] = summary
            except Exception as e:
                print(f"[ERROR] Unable to process {file_path}: {e}")
                continue
        else:
            print(f"[WARN] File does not exist: {full_path}")

    combined_tldrs = "\n\n".join(
        [f"File: {path}\nSummary: {summary}" for path, summary in summaries.items()]
    )
    if not combined_tldrs.strip():
        raise ValueError("No summaries were generated from the provided files.")
    
    print(f"[INFO] Combined TLDRs:\n{combined_tldrs}")

    project_summary = generate_lld_section(  # Assuming this function is defined
        f"Summarize the entire project based on these file summaries:\n{combined_tldrs}"
    )
    print(f"[INFO] Project Summary:\n{project_summary}\n")


    lld_markdown_content = f"# Project Summary\n\n{project_summary}\n\n"  # Initialize

    if enabled_prompts.get('generate_lld_document', False):
        for section_key, section_info in section_templates.items(): # Assuming section_templates is defined
            try:
                section_prompt = section_info['prompt'].format(
                    project_context=project_summary,
                    file_summaries=combined_tldrs
                )
                section_content = generate_lld_section(section_prompt)  # Assuming this function is defined

                lld_markdown_content += f"## {section_info['title']}\n\n{section_content}\n\n" # Add to content

            except Exception as e:
                print(f"[ERROR] Error generating section for {section_key}: {e}")
                continue

    for prompt_name, is_enabled in enabled_prompts.items():
        if prompt_name == 'generate_lld_document':
            continue

        if is_enabled:
            try:
                prompt_file_path = os.path.join("prompts", f"{prompt_name}.md") # Adjust path as needed
                if not os.path.exists(prompt_file_path):
                    print(f"[WARN] Prompt file not found: {prompt_file_path}")
                    continue

                with open(prompt_file_path, 'r', encoding='utf-8') as f:
                    prompt_text = f.read()

                formatted_prompt = prompt_text.format(
                    project_context=project_summary,
                    file_summaries=combined_tldrs
                )

                section_content = generate_lld_section(formatted_prompt)  # Assuming this function is defined
                lld_markdown_content += f"## {prompt_name.replace('_', ' ').title()}\n\n{section_content}\n\n" # Add to content

            except Exception as e:
                print(f"[ERROR] Error generating section for {prompt_name}: {e}")
                continue

    # Call markdown_to_docx *after* building the complete content
    if not lld_path:
        lld_path = os.path.join(repo_path, 'project_lld.docx')  # Or specify your desired path

    success = markdown_to_docx(lld_markdown_content, lld_path)  # Assuming this function is defined

    if success:
        print(f"[INFO] LLD document saved to {lld_path}")
        return lld_path, lld_markdown_content # Return both path and content
    else:
        print(f"[ERROR] Failed to generate LLD document.")
        return None, None  # Or raise an exception if you prefer
    
section_templates = {
    'introduction': {
        'heading': '1. Introduction',
        'title': 'Introduction',
        'prompt': """Write a comprehensive introduction that includes:
        - Purpose and scope of the system
        - Key features and functionality
        - Target audience and use cases
        - Overall system context and relationships

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}"""
    },
    'system_overview': {
        'heading': '2. System Overview',
        'title': 'System Overview',
        'prompt': """Provide a detailed system overview covering:
        - High-level architecture
        - Major components and their interactions
        - System boundaries and interfaces
        - Key design decisions and rationale

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}"""
    },
    'detailed_design': {
        'heading': '3. Detailed Design',
        'title': 'Detailed Design',
        'prompt': """Create a detailed design section including:
        - Component-level design details
        - Class/module relationships
        - Key algorithms and data structures
        - Design patterns used

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}"""
    },
    'data_design': {
        'heading': '4. Data Design',
        'title': 'Data Design',
        'prompt': """Analyze the data aspects of the code and describe:
        - Data models and structures
        - Data flow and transformations
        - Storage and retrieval mechanisms
        - Data validation and integrity

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}"""
    },
    'interface_design': {
        'heading': '5. Interface Design',
        'title': 'Interface Design',
        'prompt': """Detail the interface design including:
        - API specifications
        - User interface components
        - External system interfaces
        - Communication protocols

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}"""
    },
    'algorithm_design': {
        'heading': '6. Algorithm Design',
        'title': 'Algorithm Design',
        'prompt': """Document the key algorithms including:
        - Core processing logic
        - Performance optimization approaches
        - Complex calculations
        - Data processing workflows

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}"""
    },
    'testing': {
        'heading': '7. Testing and Validation',
        'title': 'Testing',
        'prompt': """Outline the testing strategy including:
        - Test approaches and methodologies
        - Test coverage and scenarios
        - Validation criteria
        - Quality assurance measures

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}"""
    }
}


def generate_markdown_output(repo_path, selected_files, directory_data):
    """Generate markdown output for the selected files."""
    output = f"# Codebase Analysis for: {os.path.basename(repo_path)}\n\n"
    
    # Directory structure
    output += "## Directory Structure\n\n"
    output += "```\n"
    output += generate_tree_string(directory_data, show_size=True, show_ignored=True)
    output += "```\n\n"
    
    # Selected files
    output += "## Selected Files\n\n"
    output += "```\n"
    for file_path in selected_files:
        output += f"{file_path}\n"
    output += "```\n\n"
    
    # File contents
    output += "## File Contents\n\n"
    file_contents = generate_content_string(directory_data)
    
    for file_info in file_contents:
        relative_path = os.path.relpath(file_info["path"], repo_path)
        if relative_path in selected_files:
            output += f"### {relative_path}\n\n```\n{file_info['content']}\n```\n\n"
    
    return output

def generate_tree_string(node, prefix="", is_last=True, show_size=False, show_ignored=False, use_color=False):
    """Generate a string representation of the directory tree."""
    if node.get("is_ignored", False) and not show_ignored:
        return ""

    result = prefix
    if use_color:
        result += Fore.GREEN + ("└── " if is_last else "├── ")
        result += Fore.BLUE + node["name"] + Style.RESET_ALL
    else:
        result += ("└── " if is_last else "├── ") + node["name"]

    if show_size and node["type"] == "file":
        size_str = f" ({node['size']} bytes)"
        result += Fore.YELLOW + size_str + Style.RESET_ALL if use_color else size_str

    if node.get("is_ignored", False):
        ignored_str = " [IGNORED]"
        result += Fore.RED + ignored_str + Style.RESET_ALL if use_color else ignored_str

    result += "\n"

    if node["type"] == "directory" and "children" in node:
        prefix += "    " if is_last else "│   "
        children = sorted(node["children"], key=lambda x: (x["type"] != "directory", x["name"]))
        if not show_ignored:
            children = [child for child in children if not child.get("is_ignored", False)]
        for i, child in enumerate(children):
            result += generate_tree_string(
                child,
                prefix,
                i == len(children) - 1,
                show_size,
                show_ignored,
                use_color
            )
    return result

def generate_content_string(data):
    """Generate a structured representation of file contents."""
    content = []

    def add_file_content(node, path=""):
        if node["type"] == "file" and not node.get("is_ignored", False) and node.get("content") != "[Non-text file]":
            content.append({
                "path": os.path.join(path, node["name"]),
                "content": node.get("content", "")
            })
        elif node["type"] == "directory" and "children" in node:
            for child in node["children"]:
                add_file_content(child, os.path.join(path, node["name"]))

    add_file_content(data)
    return content