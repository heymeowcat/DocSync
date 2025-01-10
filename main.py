from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from github import Github, GithubException
import uvicorn
import os

from routes import scan_project, generate_lld

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(scan_project.router)
app.include_router(generate_lld.router)

# GitHub OAuth credentials (replace with your own)
GITHUB_ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN", "your_github_access_token")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/connect_github")
async def connect_github(repo_url: str):
    """Connect to a GitHub repository and fetch its contents."""
    try:
        # Extract owner and repo name from the URL
        parts = repo_url.strip("/").split("/")
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL.")

        owner, repo_name = parts[-2], parts[-1]

        # Authenticate with GitHub
        g = Github(GITHUB_ACCESS_TOKEN)
        repo = g.get_repo(f"{owner}/{repo_name}")

        # Fetch repository contents
        contents = repo.get_contents("")
        file_tree = build_github_file_tree(contents)

        return JSONResponse({"tree": file_tree, "prompts": {}})
    except GithubException as e:
        raise HTTPException(status_code=400, detail=f"GitHub API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def build_github_file_tree(contents):
    """Build a file tree structure from GitHub repository contents."""
    file_tree = {"type": "directory", "name": "", "path": "", "children": []}

    for content in contents:
        if content.type == "dir":
            file_tree["children"].append({
                "type": "directory",
                "name": content.name,
                "path": content.path,
                "children": []
            })
        elif content.type == "file":
            file_tree["children"].append({
                "type": "file",
                "name": content.name,
                "path": content.path
            })

    return file_tree

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)