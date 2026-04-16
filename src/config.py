import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv


def _base_dir() -> Path:
    """exe로 실행 중이면 exe 위치, 개발 중이면 프로젝트 루트"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


BASE_DIR = _base_dir()
load_dotenv(dotenv_path=BASE_DIR / ".env")

WATCH_CONFIG_PATH = BASE_DIR / "config" / "watch_projects.json"


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
    if not WATCH_CONFIG_PATH.exists():
        return []
    with open(WATCH_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_watch_projects(projects: list[dict]) -> None:
    WATCH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCH_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)


def add_watch_project(project_path: str, repo_name: str, auto_push: bool = True) -> None:
    projects = load_watch_projects()
    project_path = str(Path(project_path).resolve())
    for p in projects:
        if p["path"] == project_path:
            return
    projects.append({"path": project_path, "repo_name": repo_name, "auto_push": auto_push})
    save_watch_projects(projects)


def remove_watch_project(project_path: str) -> None:
    projects = load_watch_projects()
    project_path = str(Path(project_path).resolve())
    projects = [p for p in projects if p["path"] != project_path]
    save_watch_projects(projects)


def save_env(key: str, value: str) -> None:
    """exe 옆의 .env 파일에 키-값 저장"""
    env_path = BASE_DIR / ".env"
    lines = []
    found = False
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.environ[key] = value
