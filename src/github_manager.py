import os
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def create_repo(repo_name: str, description: str = "", private: bool = False) -> str:
    """GitHub 레포지토리 생성 후 URL 반환"""
    url = "https://api.github.com/user/repos"
    data = {
        "name": repo_name,
        "description": description,
        "private": private,
        "auto_init": False,
    }
    response = requests.post(url, headers=HEADERS, json=data)

    if response.status_code == 201:
        repo_url = response.json()["html_url"]
        print(f"레포지토리 생성 완료: {repo_url}")
        return repo_url
    elif response.status_code == 422:
        print(f"이미 존재하는 레포지토리입니다: {repo_name}")
        return f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
    else:
        raise Exception(f"레포지토리 생성 실패: {response.status_code} {response.text}")


DEFAULT_GITIGNORE = """\
# 의존성
node_modules/
venv/
.venv/
__pycache__/
*.pyc
*.pyo

# 빌드 결과물
dist/
build/
*.egg-info/
.next/
out/

# 환경변수
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.suo
*.user

# OS
.DS_Store
Thumbs.db

# 로그
*.log
npm-debug.log*
"""


def _ensure_gitignore(project_dir: Path) -> None:
    """프로젝트에 .gitignore가 없으면 기본값으로 생성"""
    gitignore_path = project_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        print(f".gitignore 자동 생성: {gitignore_path}")


def upload_project(project_path: str, repo_name: str, commit_message: str = "", private: bool = False):
    """프로젝트 폴더를 GitHub 레포지토리에 업로드"""
    project_dir = Path(project_path)

    if not project_dir.exists():
        raise Exception(f"폴더가 존재하지 않습니다: {project_path}")

    if not commit_message:
        commit_message = f"upload: {repo_name} 프로젝트 업로드"

    # .gitignore 없으면 자동 생성 (node_modules 등 제외)
    _ensure_gitignore(project_dir)

    repo_url = create_repo(repo_name, private=private)
    remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{repo_name}.git"

    git_dir = project_dir / ".git"
    if not git_dir.exists():
        _run(["git", "init"], cwd=project_dir)
        _run(["git", "branch", "-M", "main"], cwd=project_dir)

    _run(["git", "add", "."], cwd=project_dir)
    _run(["git", "commit", "-m", commit_message], cwd=project_dir)

    remotes = _run(["git", "remote"], cwd=project_dir, capture=True)
    if "origin" in remotes:
        _run(["git", "remote", "set-url", "origin", remote_url], cwd=project_dir)
    else:
        _run(["git", "remote", "add", "origin", remote_url], cwd=project_dir)

    _run(["git", "push", "-u", "origin", "main"], cwd=project_dir)
    print(f"업로드 완료: {repo_url}")
    return repo_url


def update_project(project_path: str, repo_name: str, commit_message: str = "", push: bool = True):
    """이미 GitHub에 연결된 프로젝트 변경사항 커밋 및 push"""
    project_dir = Path(project_path)

    if not project_dir.exists():
        raise Exception(f"폴더가 존재하지 않습니다: {project_path}")

    # 변경사항 확인
    status = _run(["git", "status", "--porcelain"], cwd=project_dir, capture=True)
    if not status.strip():
        return  # 변경사항 없으면 스킵

    if not commit_message:
        commit_message = f"update: {repo_name} 업데이트"

    _run(["git", "add", "."], cwd=project_dir)
    _run(["git", "commit", "-m", commit_message], cwd=project_dir)

    if push:
        _run(["git", "push"], cwd=project_dir)


def _run(cmd: list, cwd: Path = None, capture: bool = False) -> str:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
    )
    if result.returncode != 0 and not capture:
        raise Exception(f"명령어 실패: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout if capture else ""