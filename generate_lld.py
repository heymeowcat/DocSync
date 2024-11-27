import os
import json
from git import Repo
from transformers import T5ForConditionalGeneration, T5Tokenizer
from docx import Document
import difflib
import logging
import torch
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load T5 model for text generation
model_name = "google/flan-t5-small"  # Use a larger model for better output
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

# Use MPS (Metal Performance Shaders) backend if available
device = "mps" if torch.backends.mps.is_available() else "cpu"
model.to(device)

def generate_folder_structure(repo_path):
    """Generate a text representation of the folder and file structure, excluding .gitignored files."""
    repo = Repo(repo_path)
    tracked_files = repo.git.ls_files().split('\n')
    untracked_files = repo.git.ls_files('--others', '--exclude-standard').split('\n')
    all_files = tracked_files + untracked_files
    
    structure = {}
    for file_path in all_files:
        if not file_path.strip():
            continue
        parts = file_path.split('/')
        current_level = structure
        for part in parts:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]
    
    def build_text(struct, indent=0):
        text = ''
        for key, value in struct.items():
            text += ' ' * indent + key + '/\n'
            if value:
                text += build_text(value, indent + 2)
        return text
    
    return build_text(structure)

def generate_tldr(file_content, file_path):
    """Generate a TLDR (summary) for a given file content using the T5 model."""
    prompt = f"""Summarize the content of the following file:
    File Path: {file_path}
    File Content: {file_content}
    """
    
    inputs = tokenizer(prompt, return_tensors="pt", max_length=2048, truncation=True).to(device)
    outputs = model.generate(**inputs, max_length=300, num_return_sequences=1)
    tldr_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return tldr_text

def generate_lld_section(prompt):
    """Generate LLD section content using T5 model"""
    inputs = tokenizer(prompt, return_tensors="pt", max_length=2048, truncation=True).to(device)
    outputs = model.generate(**inputs, max_length=1000, num_return_sequences=1)
    raw_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
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
    
    # Combine TLDRs
    combined_tldrs = "\n\n".join([diff['tldr_section'] for entry in detailed_entries for diff in entry.get('diffs', [])])
    
    # Generate LLD sections using T5 model
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


def generate_lld_from_directory(repo_path, lld_path=None):
    folder_structure = generate_folder_structure(repo_path)
    prompt = f"""Identify the key files and folders that are important for the Low-Level Design (LLD) document. List the file paths only.

    {folder_structure}
    """
    important_files_prompt = generate_lld_section(prompt)
    
    # Extract important files from model response
    important_files = [line.strip() for line in important_files_prompt.split('\n') if line.strip()]
    
    summaries = {}
    for file_path in important_files:
        full_path = os.path.join(repo_path, file_path)
        if os.path.isfile(full_path):
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            summary = generate_tldr(content, file_path)
            summaries[file_path] = summary
            print(f"Summary for {file_path}:\n{summary}\n")
    
    combined_tldrs = "\n\n".join(summaries.values())
    project_summary = generate_lld_section(f"Summarize the entire project based on these file summaries:\n{combined_tldrs}")
    print(f"Project Summary:\n{project_summary}\n")
    
    lld_sections = {}
    lld_sections['introduction'] = generate_lld_section(f"""Write a detailed introduction for the LLD document. 
    Include the purpose of the document, the scope of the system being designed, 
    and an overview of the components covered, based on this project summary:
    {project_summary}
    """)
    
    lld_sections['system_overview'] = generate_lld_section(f"""Provide a comprehensive system overview for the LLD document. 
    Describe the overall architecture, main components, their interactions, data flows, 
    key functionalities, and the operating environment, based on this project summary:
    {project_summary}
    """)

    lld_sections['detailed_design'] = generate_lld_section(f"""Provide a detailed design for the LLD document. 
    Describe the internal structure of each component, including classes, modules, and their relationships. 
    Explain the design patterns used, and provide detailed diagrams where applicable. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['data_design'] = generate_lld_section(f"""Provide a detailed data design for the LLD document. 
    Describe the data models, database schema, data storage solutions, and data flow diagrams. 
    Explain how data is managed, stored, and retrieved within the system. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['interface_design'] = generate_lld_section(f"""Provide a detailed interface design for the LLD document. 
    Describe the user interfaces, API endpoints, and communication protocols. 
    Explain how different components interact with each other and with external systems. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['algorithm_design'] = generate_lld_section(f"""Provide a detailed algorithm design for the LLD document. 
    Describe the key algorithms used in the system, including their complexity, flowcharts, and pseudocode. 
    Explain how these algorithms contribute to the system's functionality. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['security_design'] = generate_lld_section(f"""Provide a detailed security design for the LLD document. 
    Describe the security measures implemented, including authentication, authorization, encryption, and data protection. 
    Explain how security is integrated into the system's architecture. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['error_handling_and_logging'] = generate_lld_section(f"""Provide a detailed error handling and logging design for the LLD document. 
    Describe how errors are detected, handled, and logged within the system. 
    Explain the logging mechanisms and how they contribute to system monitoring and debugging. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['performance_considerations'] = generate_lld_section(f"""Provide a detailed performance considerations section for the LLD document. 
    Describe the performance metrics, optimization techniques, and load balancing strategies. 
    Explain how performance is monitored and improved within the system. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['testing_and_validation'] = generate_lld_section(f"""Provide a detailed testing and validation section for the LLD document. 
    Describe the testing strategies, test cases, and validation processes. 
    Explain how the system is tested for correctness, reliability, and performance. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['deployment_considerations'] = generate_lld_section(f"""Provide a detailed deployment considerations section for the LLD document. 
    Describe the deployment strategy, environment setup, and deployment pipelines. 
    Explain how the system is deployed and maintained in different environments. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['assumptions_and_dependencies'] = generate_lld_section(f"""Provide a detailed assumptions and dependencies section for the LLD document. 
    List and describe the key assumptions made during the design and development of the system. 
    Identify and explain the external dependencies and their impact on the system. 
    Use this project summary as a reference:
    {project_summary}
    """)

    lld_sections['appendix'] = generate_lld_section(f"""Provide an appendix section for the LLD document. 
    Include any additional information, diagrams, tables, or references that support the design and implementation of the system. 
    Use this project summary as a reference:
    {project_summary}
    """)

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
    return lld_path

def main():
    project_path = input("Enter the path to the project directory: ")
    action = input("Choose an action:\n1. Create New LLD\n2. Update Existing LLD\nEnter the number of your choice: ")
    
    if action == '1':
        lld_path = generate_lld_from_directory(project_path)
        print(f"New LLD document created at {lld_path}")
    elif action == '2':
        repo = Repo(project_path)
        branches = [branch.name for branch in repo.branches]
        print("Available branches:")
        for i, branch in enumerate(branches):
            print(f"{i + 1}. {branch}")
        
        branch_index = int(input("Select a branch by number: ")) - 1
        selected_branch = branches[branch_index]
        
        commits = list(repo.iter_commits(selected_branch))
        print("Available commits:")
        for i, commit in enumerate(commits):
            print(f"{i + 1}. {commit.hexsha} - {commit.message.strip()}")
        
        from_commit_index = int(input("Select the 'from' commit by number: ")) - 1
        to_commit_index = int(input("Select the 'to' commit by number: ")) - 1
        
        from_commit = commits[from_commit_index].hexsha
        to_commit = commits[to_commit_index].hexsha
        
        generate_detailed_commit_info(project_path, from_commit, to_commit)
        print("LLD document updated successfully.")
    else:
        print("Invalid choice.")

if __name__ == '__main__':
    main()