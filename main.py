import sys
import json
import typer

# Windows 한국어 환경 인코딩 처리
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from pathlib import Path
from typing import Optional

from src.config import (
    add_watch_project,
    remove_watch_project,
    load_watch_projects,
    save_watch_projects,
)
from src.github_manager import upload_project, update_project
from src.watcher import WatcherService

app = typer.Typer(help="GitHub 자동 업로드 툴 — VSCode 작업물을 GitHub에 자동으로 관리합니다.")


@app.command()
def init(
    path: str = typer.Argument(..., help="등록할 프로젝트 폴더 경로"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="GitHub 레포 이름 (기본값: 폴더명)"),
    auto_push: bool = typer.Option(True, "--auto-push/--no-auto-push", help="변경 감지 시 자동 push 여부"),
    private: bool = typer.Option(False, "--private", help="비공개 레포로 생성"),
):
    """프로젝트를 GitHub에 등록하고 감시 목록에 추가합니다."""
    project_dir = Path(path).resolve()
    if not project_dir.exists():
        typer.echo(f"오류: 폴더가 존재하지 않습니다 → {project_dir}", err=True)
        raise typer.Exit(1)

    repo_name = repo or project_dir.name

    typer.echo(f"[1/2] GitHub 레포 생성 및 업로드 중... ({repo_name})")
    try:
        repo_url = upload_project(str(project_dir), repo_name, private=private)
        typer.echo(f"      완료: {repo_url}")
    except Exception as e:
        typer.echo(f"오류: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"[2/2] 감시 목록 등록 중...")
    add_watch_project(str(project_dir), repo_name, auto_push)
    typer.echo(f"\n등록 완료! 이제 'watch' 명령으로 자동 감시를 시작하세요.")


@app.command()
def watch(
    debounce: int = typer.Option(5, "--debounce", "-d", help="변경 감지 후 대기 시간(초)"),
):
    """등록된 모든 프로젝트를 감시하며 변경 시 자동으로 GitHub에 업로드합니다."""
    projects = load_watch_projects()
    if not projects:
        typer.echo("등록된 프로젝트가 없습니다. 먼저 'init' 명령으로 프로젝트를 등록하세요.")
        raise typer.Exit(1)

    service = WatcherService()
    for p in projects:
        service.add_project(p["path"], p["repo_name"], p.get("auto_push", True), debounce)
    service.start()


@app.command()
def upload(
    path: str = typer.Argument(..., help="업로드할 프로젝트 폴더 경로"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="커밋 메시지"),
):
    """프로젝트를 수동으로 GitHub에 업로드/업데이트합니다."""
    project_dir = Path(path).resolve()
    if not project_dir.exists():
        typer.echo(f"오류: 폴더가 존재하지 않습니다 → {project_dir}", err=True)
        raise typer.Exit(1)

    # git 초기화 여부로 신규/업데이트 구분
    git_dir = project_dir / ".git"
    try:
        if git_dir.exists():
            typer.echo(f"업데이트 중... ({project_dir.name})")
            update_project(str(project_dir), project_dir.name, message or "", push=True)
            typer.echo("업데이트 완료!")
        else:
            typer.echo(f"초기 업로드 중... ({project_dir.name})")
            repo_url = upload_project(str(project_dir), project_dir.name, commit_message=message or "")
            typer.echo(f"업로드 완료: {repo_url}")
    except Exception as e:
        typer.echo(f"오류: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def remove(
    path: str = typer.Argument(..., help="감시 목록에서 제거할 프로젝트 경로"),
):
    """프로젝트를 감시 목록에서 제거합니다."""
    remove_watch_project(path)


@app.command()
def list_projects():
    """등록된 감시 프로젝트 목록을 출력합니다."""
    projects = load_watch_projects()
    if not projects:
        typer.echo("등록된 프로젝트가 없습니다.")
        return

    typer.echo(f"\n감시 중인 프로젝트 ({len(projects)}개):")
    for i, p in enumerate(projects, 1):
        auto = "자동push" if p.get("auto_push") else "수동push"
        typer.echo(f"  {i}. {p['repo_name']} ({auto})")
        typer.echo(f"     경로: {p['path']}")


@app.command()
def vscode_setup(
    path: str = typer.Argument(..., help="VSCode tasks.json을 생성할 프로젝트 경로"),
):
    """VSCode tasks.json을 생성하여 단축키로 GitHub 업로드를 실행할 수 있게 설정합니다."""
    project_dir = Path(path).resolve()
    vscode_dir = project_dir / ".vscode"
    vscode_dir.mkdir(exist_ok=True)

    tasks_path = vscode_dir / "tasks.json"
    tasks = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "GitHub Upload",
                "type": "shell",
                "command": f"python {Path(__file__).resolve()} upload ${{workspaceFolder}}",
                "group": "build",
                "presentation": {"reveal": "always", "panel": "shared"},
                "problemMatcher": [],
            }
        ],
    }
    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    typer.echo(f"tasks.json 생성 완료: {tasks_path}")
    typer.echo("VSCode에서 Ctrl+Shift+P → 'Run Task' → 'GitHub Upload' 로 실행할 수 있습니다.")


if __name__ == "__main__":
    app()
