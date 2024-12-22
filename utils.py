import fnmatch
import os
from os.path import join, dirname
from colorama import Fore, Style
from dotenv import load_dotenv
from docx import Document
import logging
import tiktoken
import re
from openai import OpenAI

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)


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


# Helper function to format prompt names
def format_prompt_name(filename):
    """Formats the prompt name for display."""
    name = filename[:-3]  # Remove .md extension
    name = name.replace("_", " ").title()  # Replace underscores and capitalize
    return name

# Directory tree builder
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

# Load a specific prompt content
def load_prompt_content(prompt_name):
    """Loads the content of a specific prompt file from the prompt library."""
    prompt_path = os.path.join(PROMPT_LIBRARY_DIR, prompt_name)
    if os.path.exists(prompt_path):
        with open(prompt_path, "r") as f:
            return f.read()
    else:
        raise FileNotFoundError(f"Prompt file '{prompt_name}' not found in '{PROMPT_LIBRARY_DIR}'.")

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

# Generate TLDR for a file
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

# Generate an LLD section
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

# Analyze directory structure
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
        print(f"Permission denied: {path}")

    return result

# Load ignore patterns
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

    return patterns

# Check if a file should be ignored
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

# Check if a file is a text file
def is_text_file(file_path):
    """Determines if a file is likely a text file based on its content."""
    try:
        with open(file_path, 'rb') as file:
            chunk = file.read(1024)
        return not bool(chunk.translate(None, bytes([7, 8, 9, 10, 12, 13, 27] + list(range(0x20, 0x100)))))
    except IOError:
        return False

# Read file content
def read_file_content(file_path):
    """Reads the content of a file, handling potential encoding errors."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

# Count tokens in a text string
def count_tokens(text):
    """Counts the number of tokens in a text string using tiktoken."""
    enc = tiktoken.get_encoding("cl100k_base")
    try:
        return len(enc.encode(text, disallowed_special=()))
    except Exception as e:
        print(f"Warning: Error counting tokens: {str(e)}")
        return 0

# Generate LLD document from directory
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
    
    # Hardcoded LLD sections
    lld_sections = {
        'introduction': generate_lld_section(f"Generate an introduction for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'system_overview': generate_lld_section(f"Generate a system overview for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'detailed_design': generate_lld_section(f"Generate a detailed design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'data_design': generate_lld_section(f"Generate a data design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'interface_design': generate_lld_section(f"Generate an interface design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'algorithm_design': generate_lld_section(f"Generate an algorithm design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'security_design': generate_lld_section(f"Generate a security design section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'error_handling_and_logging': generate_lld_section(f"Generate an error handling and logging section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'performance_considerations': generate_lld_section(f"Generate a performance considerations section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'testing_and_validation': generate_lld_section(f"Generate a testing and validation section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'deployment_considerations': generate_lld_section(f"Generate a deployment considerations section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'assumptions_and_dependencies': generate_lld_section(f"Generate an assumptions and dependencies section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}"),
        'appendix': generate_lld_section(f"Generate an appendix section for a Low-Level Design (LLD) document based on these TLDRs:\n{combined_tldrs}")
    }
    
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

# Generate markdown output for directory analysis
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

# Generate tree string for directory structure
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

# Generate content string for file contents
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

def format_prompt_name(filename):
    """Formats the prompt name for display."""
    name = filename[:-3]  # Remove .md extension
    name = name.replace("_", " ").title()  # Replace underscores and capitalize
    return name