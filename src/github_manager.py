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


def fetch_my_repos() -> list[dict]:
    """내 GitHub 레포지토리 목록 조회"""
    import src.config as cfg
    token = cfg.get_github_token()
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    repos = []
    page = 1
    while True:
        r = requests.get(
            f"https://api.github.com/user/repos?sort=updated&per_page=50&page={page}",
            headers=headers,
        )
        if r.status_code != 200 or not r.json():
            break
        repos.extend(r.json())
        if len(r.json()) < 50:
            break
        page += 1
    return repos


def create_release_tag(project_path: str, repo_name: str, version: str, tag_type: str, description: str) -> str:
    """git 태그 생성 + GitHub Release 발행"""
    import src.config as cfg
    token = cfg.get_github_token()
    username = cfg.get_github_username()
    project_dir = Path(project_path)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 로컬 태그 생성
    tag_message = f"{tag_type}: {description}"
    _run(["git", "tag", "-a", version, "-m", tag_message], cwd=project_dir)
    _run(["git", "push", "origin", version], cwd=project_dir)

    # GitHub Release 생성
    body = f"## {tag_type}\n\n{description}"
    r = requests.post(
        f"https://api.github.com/repos/{username}/{repo_name}/releases",
        headers=headers,
        json={
            "tag_name": version,
            "name": f"{version} — {tag_type}",
            "body": body,
            "draft": False,
            "prerelease": False,
        },
    )
    if r.status_code == 201:
        return r.json().get("html_url", "")
    raise Exception(f"Release 생성 실패: {r.status_code} {r.text}")


def delete_github_repo(repo_name: str) -> None:
    """GitHub 레포지토리 삭제"""
    import src.config as cfg
    token = cfg.get_github_token()
    username = cfg.get_github_username()
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.delete(
        f"https://api.github.com/repos/{username}/{repo_name}",
        headers=headers,
    )
    if r.status_code == 204:
        return
    elif r.status_code == 403:
        raise Exception("권한 없음 — 토큰에 delete_repo 권한이 필요합니다.")
    elif r.status_code == 404:
        raise Exception(f"레포지토리를 찾을 수 없습니다: {repo_name}")
    else:
        raise Exception(f"삭제 실패: {r.status_code}")


def get_latest_tag(project_path: str) -> str:
    """마지막 git 태그 반환 (없으면 빈 문자열)"""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=project_path, capture_output=True, text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


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

    # 변경사항 없어도 빈 커밋으로 초기화 (레포가 비어있으면 push 불가)
    staged = _run(["git", "diff", "--cached", "--name-only"], cwd=project_dir, capture=True)
    if staged.strip():
        _run(["git", "commit", "-m", commit_message], cwd=project_dir)
    else:
        _run(["git", "commit", "--allow-empty", "-m", commit_message], cwd=project_dir)

    remotes = _run(["git", "remote"], cwd=project_dir, capture=True)
    if "origin" in remotes:
        _run(["git", "remote", "set-url", "origin", remote_url], cwd=project_dir)
    else:
        _run(["git", "remote", "add", "origin", remote_url], cwd=project_dir)

    # 기존 히스토리가 있는 프로젝트면 강제 push (첫 등록이므로)
    try:
        _run(["git", "push", "-u", "origin", "main"], cwd=project_dir)
    except Exception:
        _run(["git", "push", "-u", "origin", "main", "--force"], cwd=project_dir)

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