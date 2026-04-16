import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 감시 프로젝트 목록 저장 파일
WATCH_CONFIG_PATH = Path(__file__).parent.parent / "config" / "watch_projects.json"


def get_github_token() -> str:
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("GITHUB_TOKEN이 .env에 설정되지 않았습니다.")
    return token


def get_github_username() -> str:
    username = os.getenv("GITHUB_USERNAME", "")
    if not username:
        raise ValueError("GITHUB_USERNAME이 .env에 설정되지 않았습니다.")
    return username


def load_watch_projects() -> list[dict]:
    """감시 중인 프로젝트 목록 로드"""
    if not WATCH_CONFIG_PATH.exists():
        return []
    with open(WATCH_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_watch_projects(projects: list[dict]) -> None:
    """감시 프로젝트 목록 저장"""
    WATCH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCH_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)


def add_watch_project(project_path: str, repo_name: str, auto_push: bool = True) -> None:
    """감시 프로젝트 추가"""
    projects = load_watch_projects()
    project_path = str(Path(project_path).resolve())

    # 중복 체크
    for p in projects:
        if p["path"] == project_path:
            print(f"이미 등록된 프로젝트입니다: {project_path}")
            return

    projects.append({
        "path": project_path,
        "repo_name": repo_name,
        "auto_push": auto_push,
    })
    save_watch_projects(projects)
    print(f"프로젝트 등록 완료: {project_path} → {repo_name}")


def remove_watch_project(project_path: str) -> None:
    """감시 프로젝트 제거"""
    projects = load_watch_projects()
    project_path = str(Path(project_path).resolve())
    projects = [p for p in projects if p["path"] != project_path]
    save_watch_projects(projects)
    print(f"프로젝트 제거 완료: {project_path}")
