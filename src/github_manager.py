import requests
import subprocess
from pathlib import Path


def _token() -> str:
    import src.config as cfg
    return cfg.get_github_token()


def _username() -> str:
    import src.config as cfg
    return cfg.get_github_username()


def _headers() -> dict:
    return {
        "Authorization": f"token {_token()}",
        "Accept": "application/vnd.github.v3+json",
    }


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
    gitignore_path = project_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(DEFAULT_GITIGNORE, encoding="utf-8")


def fetch_my_repos() -> list[dict]:
    """내 GitHub 레포지토리 목록 조회"""
    repos = []
    page = 1
    while True:
        r = requests.get(
            f"https://api.github.com/user/repos?sort=updated&per_page=50&page={page}",
            headers=_headers(),
        )
        if r.status_code != 200 or not r.json():
            break
        repos.extend(r.json())
        if len(r.json()) < 50:
            break
        page += 1
    return repos


def create_repo(repo_name: str, description: str = "", private: bool = False) -> str:
    """GitHub 레포지토리 생성 후 URL 반환"""
    r = requests.post(
        "https://api.github.com/user/repos",
        headers=_headers(),
        json={"name": repo_name, "description": description,
              "private": private, "auto_init": False},
    )
    if r.status_code == 201:
        return r.json()["html_url"]
    elif r.status_code == 422:
        return f"https://github.com/{_username()}/{repo_name}"
    else:
        raise Exception(f"레포지토리 생성 실패: {r.status_code} {r.text}")


def upload_project(project_path: str, repo_name: str, commit_message: str = "", private: bool = False) -> str:
    """프로젝트 폴더를 GitHub 레포지토리에 업로드"""
    project_dir = Path(project_path)
    if not project_dir.exists():
        raise Exception(f"폴더가 존재하지 않습니다: {project_path}")

    if not commit_message:
        commit_message = f"upload: {repo_name} 프로젝트 업로드"

    _ensure_gitignore(project_dir)
    repo_url = create_repo(repo_name, private=private)
    remote_url = f"https://{_token()}@github.com/{_username()}/{repo_name}.git"

    # git 초기화 (없는 경우)
    if not (project_dir / ".git").exists():
        # -b main 옵션으로 브랜치명 지정 (git 2.28+)
        result = subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=project_dir, capture_output=True, text=True,
        )
        if result.returncode != 0:
            # 구버전 git 폴백
            _run(["git", "init"], cwd=project_dir)

    _run(["git", "add", "."], cwd=project_dir)

    # 스테이징된 파일 있으면 일반 커밋, 없으면 빈 커밋
    staged = _run(["git", "diff", "--cached", "--name-only"], cwd=project_dir, capture=True)
    if staged.strip():
        _run(["git", "commit", "-m", commit_message], cwd=project_dir)
    else:
        _run(["git", "commit", "--allow-empty", "-m", commit_message], cwd=project_dir)

    # 현재 브랜치 확인 후 main으로 통일
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir, capture=True).strip()
    if branch and branch != "main":
        _run(["git", "branch", "-M", "main"], cwd=project_dir)

    # remote 설정
    remotes = _run(["git", "remote"], cwd=project_dir, capture=True)
    if "origin" in remotes:
        _run(["git", "remote", "set-url", "origin", remote_url], cwd=project_dir)
    else:
        _run(["git", "remote", "add", "origin", remote_url], cwd=project_dir)

    # push (충돌 시 강제 push)
    try:
        _run(["git", "push", "-u", "origin", "main"], cwd=project_dir)
    except Exception:
        _run(["git", "push", "-u", "origin", "main", "--force"], cwd=project_dir)

    return repo_url


def update_project(project_path: str, repo_name: str, commit_message: str = "", push: bool = True):
    """변경사항 커밋 및 push"""
    project_dir = Path(project_path)
    if not project_dir.exists():
        raise Exception(f"폴더가 존재하지 않습니다: {project_path}")

    status = _run(["git", "status", "--porcelain"], cwd=project_dir, capture=True)
    if not status.strip():
        return

    if not commit_message:
        commit_message = f"update: {repo_name} 업데이트"

    _run(["git", "add", "."], cwd=project_dir)
    _run(["git", "commit", "-m", commit_message], cwd=project_dir)
    if push:
        _run(["git", "push"], cwd=project_dir)


def create_release_tag(project_path: str, repo_name: str, version: str, tag_type: str, description: str) -> str:
    """git 태그 생성 + GitHub Release 발행"""
    project_dir = Path(project_path)
    _run(["git", "tag", "-a", version, "-m", f"{tag_type}: {description}"], cwd=project_dir)
    _run(["git", "push", "origin", version], cwd=project_dir)

    r = requests.post(
        f"https://api.github.com/repos/{_username()}/{repo_name}/releases",
        headers=_headers(),
        json={
            "tag_name": version,
            "name": f"{version} — {tag_type}",
            "body": f"## {tag_type}\n\n{description}",
            "draft": False,
            "prerelease": False,
        },
    )
    if r.status_code == 201:
        return r.json().get("html_url", "")
    raise Exception(f"Release 생성 실패: {r.status_code}")


def delete_github_repo(repo_name: str) -> None:
    """GitHub 레포지토리 삭제"""
    r = requests.delete(
        f"https://api.github.com/repos/{_username()}/{repo_name}",
        headers=_headers(),
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
    """마지막 git 태그 반환"""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=project_path, capture_output=True, text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _run(cmd: list, cwd: Path = None, capture: bool = False) -> str:
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=capture, text=True,
    )
    if result.returncode != 0 and not capture:
        raise Exception(f"git 오류: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout if capture else ""
