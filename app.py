from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from git import Repo
from transformers import T5ForConditionalGeneration, T5Tokenizer
from docx import Document
import difflib
import logging

app = FastAPI()

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Allow requests from this origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load T5 model for text generation
model_name = "google/flan-t5-small"
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

def generate_lld_content(code_changes, commit_info):
    """Generate LLD content using T5 model"""
    prompt = f"""Generate a Low-Level Design (LLD) section based on these code changes:
    Commit Message: {commit_info['message']}
    Author: {commit_info['author']}
    File Changes: {json.dumps(code_changes)}
    
    Provide detailed design insights, focusing on:
    - Module purpose
    - Responsibilities
    - Key algorithmic changes
    - Potential performance implications
    """
    
    # Tokenize the prompt
    inputs = tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
    
    # Generate LLD content
    outputs = model.generate(**inputs, max_length=300, num_return_sequences=1)
    lld_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    return lld_text

def get_commit_hashes(repo_path):
    repo = Repo(repo_path)
    return [str(commit) for commit in list(repo.iter_commits())]

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
        # Basic commit information
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
                    blob_old = old_commit_obj[d.a_path]
                    blob_new = new_commit_obj[d.a_path]
                    
                    old_content = blob_old.data_stream.read().decode('utf-8', errors='ignore').splitlines()
                    new_content = blob_new.data_stream.read().decode('utf-8', errors='ignore').splitlines()
                    
                    diff_lines = list(difflib.unified_diff(
                        old_content, 
                        new_content, 
                        fromfile=f'a/{d.a_path}', 
                        tofile=f'b/{d.a_path}'
                    ))
                    
                    # Generate LLD for this specific change
                    lld_section = generate_lld_content(file_change, entry)
                    
                    diffs.append({
                        'file': d.a_path,
                        'diff_content': diff_lines,
                        'lld_section': lld_section
                    })
                except Exception as e:
                    logger.error(f"Error processing {d.a_path}: {e}")
        
        entry['file_changes'] = file_changes
        entry['diffs'] = diffs
        detailed_entries.append(entry)
    
    # Create LLD document
    if not lld_path:
        lld_path = os.path.join(repo_path, 'project_lld.docx')
    
    doc = Document()
    doc.add_heading('Low-Level Design (LLD) Document', 0)
    
    for entry in detailed_entries:
        doc.add_heading(f'Commit: {entry["commit_hash"]}', level=1)
        doc.add_paragraph(f'Message: {entry["message"]}')
        doc.add_paragraph(f'Author: {entry["author"]} <{entry["email"]}>')
        doc.add_paragraph(f'Date: {entry["date"]}')
        
        for diff in entry.get('diffs', []):
            doc.add_heading(f'File: {diff["file"]}', level=2)
            doc.add_paragraph('Changes:')
            doc.add_paragraph('\n'.join(diff['diff_content']))
            
            doc.add_heading('LLD Insights', level=3)
            doc.add_paragraph(diff['lld_section'])
    
    doc.save(lld_path)
    
    return {
        'detailed_entries': detailed_entries,
        'lld_path': lld_path
    }

@app.post("/get-branches")
async def get_branches(request: Request):
    data = await request.json()
    repo_path = data['filePath']
    logger.debug(f"Fetching branches for repo path: {repo_path}")
    repo = Repo(repo_path)
    branches = [branch.name for branch in repo.branches]
    return JSONResponse({'branches': branches})

@app.post("/get-commits")
async def get_commits(request: Request):
    data = await request.json()
    branch_name = data['branchName']
    repo_path = data['repoPath']
    logger.debug(f"Fetching commits for branch: {branch_name} in repo path: {repo_path}")
    repo = Repo(repo_path)
    commits = [
        {
            'hash': str(commit),
            'message': commit.message,
            'author': commit.author.name,
            'date': commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
        for commit in repo.iter_commits(branch_name)
    ]
    return JSONResponse({'commits': commits})

@app.post("/compare-commits")
async def compare_commits(request: Request):
    data = await request.json()
    from_hash = data['fromHash']
    to_hash = data['toHash']
    repo_path = data['repoPath']
    logger.debug(f"Comparing commits from {from_hash} to {to_hash} in repo path: {repo_path}")
    repo = Repo(repo_path)
    
    old_commit_obj = repo.commit(from_hash)
    new_commit_obj = repo.commit(to_hash)
    
    diffs = []
    
    for d in old_commit_obj.diff(new_commit_obj):
        change_type = {
            'A': 'Added',
            'D': 'Deleted',
            'M': 'Modified',
            'R': 'Renamed'
        }.get(d.change_type, 'Unknown')
        
        if change_type == 'Modified':
            try:
                blob_old = old_commit_obj[d.a_path]
                blob_new = new_commit_obj[d.a_path]
                
                old_content = blob_old.data_stream.read().decode('utf-8', errors='ignore').splitlines()
                new_content = blob_new.data_stream.read().decode('utf-8', errors='ignore').splitlines()
                
                diff_lines = list(difflib.unified_diff(
                    old_content, 
                    new_content, 
                    fromfile=f'a/{d.a_path}', 
                    tofile=f'b/{d.a_path}'
                ))
                
                diffs.append({
                    'file': d.a_path,
                    'diff_content': diff_lines
                })
            except Exception as e:
                logger.error(f"Error processing {d.a_path}: {e}")
    
    return JSONResponse({'diffs': diffs})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)