"""Core utilities for scanning projects and generating LLD documents."""

from __future__ import annotations

import datetime
import fnmatch
import logging
import os
import re
from os.path import dirname, join

import pypandoc
import tiktoken

try:
    from colorama import Fore, Style
except ImportError:  # pragma: no cover - optional dependency

    class _NoColor:
        def __getattr__(self, _name):
            return ""

    Fore = Style = _NoColor()
from dotenv import load_dotenv
from git import Repo
from openai import OpenAI

from config import settings

load_dotenv(join(dirname(__file__), ".env"))

logger = logging.getLogger(__name__)

client = OpenAI(
    base_url=settings.openrouter_base_url,
    api_key=settings.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", ""),
)

# Default ignore patterns
DEFAULT_IGNORE_PATTERNS = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "__pycache__",  # Python
    "node_modules",
    "bower_components",  # JavaScript
    ".git",
    ".svn",
    ".hg",
    ".gitignore",  # Version control
    "venv",
    ".venv",
    "env",  # Virtual environments
    ".idea",
    ".vscode",  # IDEs
    "*.log",
    "*.bak",
    "*.swp",
    "*.tmp",  # Temporary and log files
    ".DS_Store",  # macOS
    "Thumbs.db",  # Windows
    "build",
    "dist",  # Build directories
    "*.egg-info",  # Python egg info
    "*.so",
    "*.dylib",
    "*.dll",  # Compiled libraries
]

PROMPT_LIBRARY_DIR = "prompt_library"  # Directory for the prompt library


def get_git_history(repo_path):
    """
    Get the Git commit history of the repository
    Returns a list of dictionaries containing commit information
    """
    try:
        repo = Repo(repo_path)
        commits = []
        for commit in repo.iter_commits():
            commits.append(
                {
                    "hash": commit.hexsha,
                    "author": commit.author.name,
                    "date": datetime.datetime.fromtimestamp(commit.committed_date).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "message": commit.message.strip(),
                    "files": [item.a_path for item in commit.diff(commit.parents[0])]
                    if commit.parents
                    else [],
                }
            )
        return commits
    except Exception as e:
        logger.warning("Error getting git history: %s", e)
        return []


def markdown_to_docx(markdown_content, output_path):
    """Convert markdown content to DOCX using pandoc."""
    try:
        # Convert markdown to docx using pandoc
        pypandoc.convert_text(
            markdown_content,
            "docx",
            outputfile=output_path,
            format="md",
            extra_args=["--standalone", "--wrap=none"],
        )
        return True
    except Exception as e:
        logger.warning("Error converting markdown to docx: %s", e)
        return False


# Helper function to format prompt names
def format_prompt_name(filename):
    """Formats the prompt name for display."""
    name = filename[:-3]  # Remove .md extension
    name = name.replace("_", " ").title()  # Replace underscores and capitalize
    return name


def get_directory_tree(path: str, base_path: str | None = None):
    """Recursively builds a directory tree structure.

    File paths are stored relative to ``base_path`` (defaults to ``path``) so
    that selected files can be resolved against the project root later.
    """
    if base_path is None:
        base_path = path
    tree = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir():
                    tree.append(
                        {
                            "type": "directory",
                            "name": entry.name,
                            "path": os.path.relpath(entry.path, base_path),
                            "children": get_directory_tree(entry.path, base_path),
                        }
                    )
                elif entry.is_file():
                    tree.append(
                        {
                            "type": "file",
                            "name": entry.name,
                            "path": os.path.relpath(entry.path, base_path),
                        }
                    )
    except Exception as e:  # noqa: BLE001
        logger.warning("Error accessing %s: %s", path, e)
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
            with open(filepath) as f:
                content = f.read()
                prompts[filename] = content
    return prompts


def generate_folder_structure_from_upload(repo_path, ignore_patterns):
    """Generates a nested dictionary representing the folder structure."""
    structure = {"name": os.path.basename(repo_path), "type": "directory", "children": []}

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [
            d for d in dirs if not should_ignore(os.path.join(root, d), repo_path, ignore_patterns)
        ]

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
                current_level["children"].append(
                    {"name": file, "type": "file", "path": os.path.join(rel_path, file)}
                )

        for dir_name in dirs:
            current_level["children"].append(
                {"name": dir_name, "type": "directory", "children": []}
            )

    return structure


def generate_tldr(file_content, file_path):
    """Generate a TLDR summary for a file."""
    prompt = (
        "Summarize the content of the following file concisely. "
        "Focus on purpose, key classes/functions, and dependencies.\n\n"
        f"File Path: {file_path}\n"
        f"File Content:\n{file_content}\n"
    )
    try:
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to generate TLDR for %s: %s", file_path, exc)
        return ""


def generate_lld_section(prompt):
    """Generate an LLD section based on a prompt."""
    try:
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.choices[0].message.content
        filtered_text = re.sub(r"<.*?>", "", raw_text).strip()
        return filtered_text
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to generate LLD section: %s", exc)
        return ""


def analyze_directory(
    path, ignore_patterns, base_path, include_git=False, max_depth=None, current_depth=0
):
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
        "path": path,
    }

    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)

            if item == ".git" and not include_git:
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
                    "path": item_path,
                }
                result["children"].append(child)
                if not is_ignored:
                    result["size"] += file_size
                    result["total_tokens"] += tokens
                    result["file_count"] += 1
                    if is_text:
                        result["text_content_size"] += len(content)
            elif os.path.isdir(item_path):
                subdir = analyze_directory(
                    item_path, ignore_patterns, base_path, include_git, max_depth, current_depth + 1
                )
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
        logger.warning("Permission denied: %s", path)

    return result


def load_ignore_patterns(base_path):
    """Load ignore patterns from default and custom ignore files."""
    patterns = set(DEFAULT_IGNORE_PATTERNS)

    for ignore_file in [".cdigestignore", ".gitignore"]:
        ignore_path = os.path.join(base_path, ignore_file)
        if os.path.exists(ignore_path):
            with open(ignore_path) as f:
                patterns.update(
                    line.strip() for line in f if line.strip() and not line.startswith("#")
                )

    return patterns


def should_ignore(path, base_path, ignore_patterns):
    """Check if a file or directory should be ignored."""
    name = os.path.basename(path)
    rel_path = os.path.relpath(path, base_path)
    abs_path = os.path.abspath(path)

    for pattern in ignore_patterns:
        if (
            fnmatch.fnmatch(name, pattern)
            or fnmatch.fnmatch(rel_path, pattern)
            or fnmatch.fnmatch(abs_path, pattern)
            or (
                pattern.startswith("/")
                and fnmatch.fnmatch(abs_path, os.path.join(base_path, pattern[1:]))
            )
            or any(fnmatch.fnmatch(part, pattern) for part in rel_path.split(os.sep))
        ):
            return True
    return False


def is_text_file(file_path):
    """Check if a file is a text file."""
    try:
        with open(file_path, "rb") as file:
            chunk = file.read(1024)
        return not bool(
            chunk.translate(None, bytes([7, 8, 9, 10, 12, 13, 27] + list(range(0x20, 0x100))))
        )
    except OSError:
        return False


def read_file_content(file_path):
    """Read file content safely."""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def count_tokens(text):
    """Count tokens in text using tiktoken."""
    enc = tiktoken.get_encoding("cl100k_base")
    try:
        return len(enc.encode(text, disallowed_special=()))
    except Exception as e:
        logger.warning("Error counting tokens: %s", e)
        return 0


def generate_lld_from_directory(repo_path, selected_files, enabled_prompts, lld_path=None):
    """Generate an LLD document from the selected files.

    ``selected_files`` may contain paths relative to ``repo_path`` or absolute
    paths. Prompts are loaded from the bundled ``prompt_library`` directory.
    """
    repo_path = os.path.abspath(repo_path)
    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
    if not selected_files:
        raise ValueError("No files selected for analysis")

    git_history = get_git_history(repo_path)
    commit_context = "\n".join(
        f"Commit: {c['hash'][:8]} | {c['date']} | {c['author']}\n{c['message']}\n"
        for c in git_history
    )

    summaries = {}
    for file_path in selected_files:
        # Resolve relative paths against the repository root.
        if os.path.isabs(file_path):
            full_path = file_path
        else:
            full_path = os.path.join(repo_path, file_path)
        full_path = os.path.normpath(full_path)

        logger.info("Processing file: %s", full_path)
        if not os.path.isfile(full_path):
            logger.warning("File does not exist: %s", full_path)
            continue
        try:
            with open(full_path, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except OSError as exc:
            logger.error("Unable to read %s: %s", full_path, exc)
            continue
        if not content.strip():
            logger.warning("File is empty or unreadable: %s", full_path)
            continue
        summary = generate_tldr(content, file_path)
        if not summary:
            logger.warning("No summary generated for %s", file_path)
            continue
        summaries[file_path] = summary

    combined_tldrs = "\n\n".join(
        f"File: {path}\nSummary: {summary}" for path, summary in summaries.items()
    )
    if not combined_tldrs.strip():
        raise ValueError("No summaries were generated from the provided files.")

    project_summary = generate_lld_section(
        "Summarize the entire project based on these file summaries and git history.\n\n"
        "File Summaries:\n"
        f"{combined_tldrs}\n\n"
        "Git History:\n"
        f"{commit_context}"
    )
    if not project_summary:
        project_summary = "Project summary could not be generated."

    lld_markdown_content = f"# Project Summary\n\n{project_summary}\n\n"

    enabled = enabled_prompts or {}
    if enabled.get("generate_lld_document", False):
        for section_key, section_info in section_templates.items():
            try:
                section_prompt = section_info["prompt"].format(
                    project_context=project_summary,
                    file_summaries=combined_tldrs,
                )
                section_content = generate_lld_section(section_prompt)
                if section_content:
                    lld_markdown_content += f"## {section_info['title']}\n\n{section_content}\n\n"
            except Exception as exc:  # noqa: BLE001
                logger.error("Error generating section %s: %s", section_key, exc)
                continue

    # Extra prompts from the prompt library (files selected by the user).
    prompt_library = load_prompts_from_library()
    for prompt_name, is_enabled in enabled.items():
        if prompt_name == "generate_lld_document" or not is_enabled:
            continue
        prompt_text = prompt_library.get(prompt_name)
        if not prompt_text:
            # Fall back to a file on disk named like the prompt.
            candidate = os.path.join(PROMPT_LIBRARY_DIR, prompt_name)
            if not candidate.endswith(".md"):
                candidate += ".md"
            if os.path.exists(candidate):
                with open(candidate, encoding="utf-8") as fh:
                    prompt_text = fh.read()
        if not prompt_text:
            logger.warning("Prompt not found: %s", prompt_name)
            continue
        try:
            formatted_prompt = prompt_text.format(
                project_context=project_summary,
                file_summaries=combined_tldrs,
            )
        except (KeyError, ValueError):
            # Prompt templates without placeholders are used verbatim.
            formatted_prompt = prompt_text
        section_content = generate_lld_section(formatted_prompt)
        if section_content:
            title = prompt_name.replace("_", " ").replace(".md", "").title()
            lld_markdown_content += f"## {title}\n\n{section_content}\n\n"

    if not lld_path:
        lld_path = os.path.join(repo_path, "project_lld.docx")

    success = markdown_to_docx(lld_markdown_content, lld_path)
    if success:
        logger.info("LLD document saved to %s", lld_path)
        return lld_path, lld_markdown_content
    logger.error("Failed to generate LLD document.")
    return None, None


section_templates = {
    "introduction": {
        "heading": "1. Introduction",
        "title": "Introduction",
        "prompt": """Write a comprehensive introduction that includes:
        - Purpose and scope of the system
        - Key features and functionality
        - Target audience and use cases
        - Overall system context and relationships

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}""",
    },
    "system_overview": {
        "heading": "2. System Overview",
        "title": "System Overview",
        "prompt": """Provide a detailed system overview covering:
        - High-level architecture
        - Major components and their interactions
        - System boundaries and interfaces
        - Key design decisions and rationale

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}""",
    },
    "detailed_design": {
        "heading": "3. Detailed Design",
        "title": "Detailed Design",
        "prompt": """Create a detailed design section including:
        - Component-level design details
        - Class/module relationships
        - Key algorithms and data structures
        - Design patterns used

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}""",
    },
    "data_design": {
        "heading": "4. Data Design",
        "title": "Data Design",
        "prompt": """Analyze the data aspects of the code and describe:
        - Data models and structures
        - Data flow and transformations
        - Storage and retrieval mechanisms
        - Data validation and integrity

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}""",
    },
    "interface_design": {
        "heading": "5. Interface Design",
        "title": "Interface Design",
        "prompt": """Detail the interface design including:
        - API specifications
        - User interface components
        - External system interfaces
        - Communication protocols

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}""",
    },
    "algorithm_design": {
        "heading": "6. Algorithm Design",
        "title": "Algorithm Design",
        "prompt": """Document the key algorithms including:
        - Core processing logic
        - Performance optimization approaches
        - Complex calculations
        - Data processing workflows

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}""",
    },
    "testing": {
        "heading": "7. Testing and Validation",
        "title": "Testing",
        "prompt": """Outline the testing strategy including:
        - Test approaches and methodologies
        - Test coverage and scenarios
        - Validation criteria
        - Quality assurance measures

        Project Context:
        {project_context}

        File Summaries:
        {file_summaries}""",
    },
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


def generate_tree_string(
    node, prefix="", is_last=True, show_size=False, show_ignored=False, use_color=False
):
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
                child, prefix, i == len(children) - 1, show_size, show_ignored, use_color
            )
    return result


def generate_content_string(data):
    """Generate a structured representation of file contents."""
    content = []

    def add_file_content(node, path=""):
        if (
            node["type"] == "file"
            and not node.get("is_ignored", False)
            and node.get("content") != "[Non-text file]"
        ):
            content.append(
                {"path": os.path.join(path, node["name"]), "content": node.get("content", "")}
            )
        elif node["type"] == "directory" and "children" in node:
            for child in node["children"]:
                add_file_content(child, os.path.join(path, node["name"]))

    add_file_content(data)
    return content
