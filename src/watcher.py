import time
import threading
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from src.github_manager import upload_project, update_project


# 무시할 파일/폴더 패턴
IGNORE_PATTERNS = {
    ".git", "__pycache__", ".pytest_cache", "venv", "node_modules",
    ".env", "*.pyc", "*.pyo", "*.log", ".DS_Store", "Thumbs.db",
}


def _should_ignore(path: str) -> bool:
    p = Path(path)
    for part in p.parts:
        if part in IGNORE_PATTERNS:
            return True
    if p.suffix in {".pyc", ".pyo", ".log"}:
        return True
    return False


class ProjectEventHandler(FileSystemEventHandler):
    """파일 변경 감지 후 debounce 적용, GitHub push 실행"""

    def __init__(self, project_path: str, repo_name: str, auto_push: bool, debounce_sec: int = 5, log_callback=None):
        self.project_path = project_path
        self.repo_name = repo_name
        self.auto_push = auto_push
        self.debounce_sec = debounce_sec
        self._timer: threading.Timer | None = None
        self._changed_files: set[str] = set()
        self._lock = threading.Lock()
        self._log = log_callback or print

    def on_any_event(self, event):
        if event.is_directory:
            return
        if _should_ignore(event.src_path):
            return

        with self._lock:
            self._changed_files.add(event.src_path)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_sec, self._flush)
            self._timer.start()

    def _flush(self):
        with self._lock:
            if not self._changed_files:
                return
            changed = list(self._changed_files)
            self._changed_files.clear()

        commit_message = _generate_commit_message(changed)
        self._log(f"변경 감지 {len(changed)}개 파일 → {self.repo_name}")
        self._log(f"커밋: {commit_message}")

        try:
            update_project(self.project_path, self.repo_name, commit_message, push=self.auto_push)
            self._log(f"{'push 완료' if self.auto_push else '커밋 완료 (push 대기)'}: {self.repo_name}")
        except Exception as e:
            self._log(f"오류: {e}")


def _generate_commit_message(changed_files: list[str]) -> str:
    """변경된 파일 목록 기반 커밋 메시지 자동 생성"""
    if len(changed_files) == 1:
        fname = Path(changed_files[0]).name
        return f"update: {fname} 수정"

    extensions = {Path(f).suffix for f in changed_files if Path(f).suffix}
    dirs = {Path(f).parent.name for f in changed_files}

    if len(dirs) == 1:
        return f"update: {list(dirs)[0]}/ 파일 {len(changed_files)}개 수정"
    return f"update: 파일 {len(changed_files)}개 수정 ({', '.join(sorted(extensions))})"


class WatcherService:
    """여러 프로젝트를 동시에 감시하는 서비스"""

    def __init__(self, log_callback=None):
        self._observers: list[Observer] = []
        self._log = log_callback or print
        self._running = False

    def add_project(self, project_path: str, repo_name: str, auto_push: bool = True, debounce_sec: int = 5):
        handler = ProjectEventHandler(project_path, repo_name, auto_push, debounce_sec, log_callback=self._log)
        observer = Observer()
        observer.schedule(handler, project_path, recursive=True)
        self._observers.append(observer)
        self._log(f"감시 등록: {repo_name}")

    def start(self):
        if not self._observers:
            self._log("감시할 프로젝트가 없습니다.")
            return
        self._running = True
        for obs in self._observers:
            obs.start()
        self._log(f"총 {len(self._observers)}개 프로젝트 감시 시작")
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self._running = False
        for obs in self._observers:
            obs.stop()
        for obs in self._observers:
            obs.join()
        self._log("감시 종료")
