import sys
import threading
import queue
from pathlib import Path
from datetime import datetime
from tkinter import filedialog, messagebox
import tkinter as tk

import customtkinter as ctk

from src.config import (
    load_watch_projects,
    add_watch_project,
    remove_watch_project,
    get_github_token,
    get_github_username,
    save_env,
)
from src.github_manager import upload_project, update_project
from src.watcher import WatcherService

# Windows 인코딩 (windowed exe에서는 stdout/stderr가 None)
if sys.platform == "win32":
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding="utf-8")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# 색상 팔레트
COLOR_BG = "#1a1a2e"
COLOR_SIDEBAR = "#16213e"
COLOR_CARD = "#0f3460"
COLOR_CARD_HOVER = "#1a4a80"
COLOR_ACCENT = "#4f8ef7"
COLOR_SUCCESS = "#4caf50"
COLOR_WARNING = "#ff9800"
COLOR_DANGER = "#f44336"
COLOR_TEXT = "#e0e0e0"
COLOR_TEXT_DIM = "#8892b0"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GitHub Auto Upload")
        self.geometry("960x620")
        self.minsize(800, 520)
        self.configure(fg_color=COLOR_BG)

        self._watcher_service: WatcherService | None = None
        self._watch_thread: threading.Thread | None = None
        self._is_watching = False
        self._log_queue: queue.Queue = queue.Queue()
        self._current_page = "dashboard"
        self._last_push_ts: str = ""
        self._last_verified_username: str = ""

        self._build_layout()
        self._show_page("dashboard")
        self._refresh_log_loop()

    # ──────────────────────────────────────────
    # 레이아웃 구성
    # ──────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 사이드바
        self._sidebar = ctk.CTkFrame(self, width=200, fg_color=COLOR_SIDEBAR, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsw")
        self._sidebar.grid_propagate(False)
        self._build_sidebar()

        # 메인 콘텐츠
        self._content = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

    def _build_sidebar(self):
        self._sidebar.grid_rowconfigure(8, weight=1)

        # 로고
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(24, 8), sticky="w")
        ctk.CTkLabel(logo_frame, text="⬡", font=ctk.CTkFont(size=28), text_color=COLOR_ACCENT).pack(side="left")
        ctk.CTkLabel(logo_frame, text=" AutoPush", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_TEXT).pack(side="left")

        # 상태 뱃지
        self._status_badge = ctk.CTkLabel(
            self._sidebar, text="● 대기 중",
            font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM,
        )
        self._status_badge.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        # 구분선
        ctk.CTkFrame(self._sidebar, height=1, fg_color="#2a3a5e").grid(row=2, column=0, sticky="ew", padx=16, pady=4)

        # 네비게이션 버튼
        nav_items = [
            ("dashboard", "  대시보드", "◈"),
            ("projects",  "  프로젝트", "◉"),
            ("log",       "  활동 로그", "◎"),
            ("settings",  "  설정",    "◇"),
        ]
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for i, (key, label, icon) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"{icon}{label}",
                font=ctk.CTkFont(size=13),
                anchor="w",
                fg_color="transparent",
                text_color=COLOR_TEXT_DIM,
                hover_color="#1e2d50",
                height=40,
                corner_radius=8,
                command=lambda k=key: self._show_page(k),
            )
            btn.grid(row=3 + i, column=0, padx=12, pady=2, sticky="ew")
            self._nav_buttons[key] = btn

        # 하단 감시 토글
        ctk.CTkFrame(self._sidebar, height=1, fg_color="#2a3a5e").grid(row=8, column=0, sticky="ew", padx=16, pady=4)
        self._watch_btn = ctk.CTkButton(
            self._sidebar,
            text="▶  감시 시작",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color="#3a7ae4",
            height=40,
            corner_radius=8,
            command=self._toggle_watch,
        )
        self._watch_btn.grid(row=9, column=0, padx=12, pady=(4, 20), sticky="ew")

    # ──────────────────────────────────────────
    # 페이지 전환
    # ──────────────────────────────────────────

    def _show_page(self, key: str):
        self._current_page = key
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(fg_color="#1e3a6e", text_color=COLOR_ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_DIM)

        for widget in self._content.winfo_children():
            widget.destroy()

        if key == "dashboard":
            self._page_dashboard()
        elif key == "projects":
            self._page_projects()
        elif key == "log":
            self._page_log()
        elif key == "settings":
            self._page_settings()

    # ──────────────────────────────────────────
    # 대시보드 페이지
    # ──────────────────────────────────────────

    def _page_dashboard(self):
        frame = self._make_page_frame("대시보드")
        projects = load_watch_projects()

        # 계정 연동 카드
        self._build_account_card(frame)

        # 요약 카드 3개
        summary_frame = ctk.CTkFrame(frame, fg_color="transparent")
        summary_frame.pack(fill="x", padx=24, pady=(0, 20))
        summary_frame.grid_columnconfigure((0, 1, 2), weight=1)

        cards = [
            ("등록 프로젝트", str(len(projects)), COLOR_ACCENT),
            ("감시 상태", "실행 중" if self._is_watching else "대기 중", COLOR_SUCCESS if self._is_watching else COLOR_TEXT_DIM),
            ("마지막 push", self._last_push_time(), COLOR_TEXT),
        ]
        for col, (title, value, color) in enumerate(cards):
            card = ctk.CTkFrame(summary_frame, fg_color=COLOR_CARD, corner_radius=12)
            card.grid(row=0, column=col, padx=6, pady=4, sticky="ew")
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=22, weight="bold"), text_color=color).pack(pady=(16, 2))
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM).pack(pady=(0, 16))

        # 프로젝트 목록 미리보기
        ctk.CTkLabel(frame, text="등록된 프로젝트", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=24, pady=(0, 8))

        if not projects:
            ctk.CTkLabel(frame, text="등록된 프로젝트가 없습니다.\n프로젝트 탭에서 추가해주세요.", text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=13)).pack(pady=30)
        else:
            for p in projects:
                self._project_card(frame, p, compact=True)

    def _build_account_card(self, parent):
        """GitHub 계정 연동 상태 카드"""
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=12)
        card.pack(fill="x", padx=24, pady=(0, 16))

        # 아바타 원형 (이니셜)
        try:
            username = get_github_username()
            initial = username[0].upper()
        except Exception:
            username = "미설정"
            initial = "?"

        avatar = ctk.CTkLabel(
            card, text=initial,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white",
            fg_color=COLOR_ACCENT,
            width=48, height=48,
            corner_radius=24,
        )
        avatar.grid(row=0, column=0, rowspan=2, padx=(20, 12), pady=16)

        # 인사말
        ctk.CTkLabel(
            card,
            text=f"{username} 님, 안녕하세요!",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).grid(row=0, column=1, sticky="sw", pady=(16, 2))

        # 연동 상태 (비동기 검증)
        self._account_status_label = ctk.CTkLabel(
            card,
            text="● 연결 확인 중...",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_DIM,
            anchor="w",
        )
        self._account_status_label.grid(row=1, column=1, sticky="nw", pady=(0, 16))

        # GitHub 프로필 링크 버튼
        ctk.CTkLabel(
            card,
            text=f"github.com/{username}",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_DIM,
            anchor="e",
        ).grid(row=0, column=2, rowspan=2, padx=(0, 20), sticky="e")

        card.grid_columnconfigure(1, weight=1)

        # 백그라운드에서 토큰 유효성 검증
        threading.Thread(target=self._verify_github_account, daemon=True).start()

    def _verify_github_account(self):
        """GitHub API로 토큰 유효성 실제 검증"""
        import requests as req
        try:
            token = get_github_token()
            r = req.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                timeout=5,
            )
            if r.status_code == 200:
                data = r.json()
                login = data.get("login", "")
                repos = data.get("public_repos", 0)
                msg = f"● 연동됨  |  공개 레포 {repos}개"
                color = COLOR_SUCCESS
                self._last_verified_username = login
            elif r.status_code == 401:
                msg = "● 토큰 인증 실패 — 설정에서 토큰을 확인하세요"
                color = COLOR_DANGER
            else:
                msg = f"● 연결 오류 ({r.status_code})"
                color = COLOR_WARNING
        except Exception as e:
            msg = "● GitHub 연결 불가"
            color = COLOR_DANGER

        # UI는 메인 스레드에서만 업데이트
        self.after(0, lambda: self._update_account_status(msg, color))

    def _update_account_status(self, msg: str, color: str):
        if hasattr(self, "_account_status_label") and self._account_status_label.winfo_exists():
            self._account_status_label.configure(text=msg, text_color=color)

    def _last_push_time(self) -> str:
        if not hasattr(self, "_last_push_ts") or not self._last_push_ts:
            return "없음"
        return self._last_push_ts

    # ──────────────────────────────────────────
    # 프로젝트 페이지
    # ──────────────────────────────────────────

    def _page_projects(self):
        frame = self._make_page_frame("프로젝트 관리")

        # 추가 버튼
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkButton(
            btn_frame, text="+ 프로젝트 추가",
            font=ctk.CTkFont(size=13), fg_color=COLOR_ACCENT, hover_color="#3a7ae4",
            height=38, corner_radius=8, command=self._add_project_dialog,
        ).pack(side="left")

        # 프로젝트 목록
        projects = load_watch_projects()
        if not projects:
            ctk.CTkLabel(frame, text="등록된 프로젝트가 없습니다.", text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=13)).pack(pady=40)
        else:
            scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
            scroll.pack(fill="both", expand=True, padx=24, pady=0)
            for p in projects:
                self._project_card(scroll, p, compact=False, removable=True)

    def _project_card(self, parent, p: dict, compact: bool, removable: bool = False):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=12)
        card.pack(fill="x", padx=0, pady=5)
        card.grid_columnconfigure(1, weight=1)

        # 아이콘
        ctk.CTkLabel(card, text="📁", font=ctk.CTkFont(size=20)).grid(row=0, column=0, rowspan=2, padx=(16, 8), pady=14)

        # 이름 + 경로
        ctk.CTkLabel(card, text=p["repo_name"], font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_TEXT, anchor="w").grid(row=0, column=1, sticky="w", pady=(12, 0))
        if not compact:
            ctk.CTkLabel(card, text=p["path"], font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM, anchor="w").grid(row=1, column=1, sticky="w", pady=(0, 12))

        # 상태 뱃지
        auto_text = "자동 push" if p.get("auto_push") else "수동 push"
        ctk.CTkLabel(card, text=auto_text, font=ctk.CTkFont(size=11),
                     text_color=COLOR_SUCCESS, fg_color="#1a3a20", corner_radius=6).grid(row=0, column=2, padx=12, pady=14)

        # 수동 push 버튼
        if not compact:
            ctk.CTkButton(
                card, text="↑ Push",
                font=ctk.CTkFont(size=12), fg_color="#1e3a6e", hover_color=COLOR_CARD_HOVER,
                height=30, width=70, corner_radius=6,
                command=lambda path=p["path"], repo=p["repo_name"]: self._manual_push(path, repo),
            ).grid(row=0, column=3, padx=4, pady=14)

        # 제거 버튼
        if removable:
            ctk.CTkButton(
                card, text="✕",
                font=ctk.CTkFont(size=12), fg_color="transparent", hover_color=COLOR_DANGER,
                text_color=COLOR_TEXT_DIM, height=30, width=36, corner_radius=6,
                command=lambda path=p["path"]: self._remove_project(path),
            ).grid(row=0, column=4, padx=(0, 12), pady=14)

    # ──────────────────────────────────────────
    # 활동 로그 페이지
    # ──────────────────────────────────────────

    def _page_log(self):
        frame = self._make_page_frame("활동 로그")

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkButton(btn_frame, text="로그 지우기", font=ctk.CTkFont(size=12),
                      fg_color="#2a3a5e", hover_color="#3a4a6e", height=32, corner_radius=6,
                      command=self._clear_log).pack(side="left")

        self._log_box = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="Consolas", size=12),
                                       fg_color="#0d1117", text_color="#58a6ff", corner_radius=10)
        self._log_box.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        self._log_box.insert("end", self._log_buffer if hasattr(self, "_log_buffer") else "")
        self._log_box.configure(state="disabled")

    def _append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        if not hasattr(self, "_log_buffer"):
            self._log_buffer = ""
        self._log_buffer += line
        if hasattr(self, "_log_box") and self._log_box.winfo_exists():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", line)
            self._log_box.see("end")
            self._log_box.configure(state="disabled")

    def _clear_log(self):
        self._log_buffer = ""
        if hasattr(self, "_log_box") and self._log_box.winfo_exists():
            self._log_box.configure(state="normal")
            self._log_box.delete("1.0", "end")
            self._log_box.configure(state="disabled")

    def _refresh_log_loop(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self._append_log(msg)
                if "push 완료" in msg:
                    self._last_push_ts = datetime.now().strftime("%H:%M")
        except queue.Empty:
            pass
        self.after(500, self._refresh_log_loop)

    # ──────────────────────────────────────────
    # 설정 페이지
    # ──────────────────────────────────────────

    def _page_settings(self):
        frame = self._make_page_frame("설정")

        card = ctk.CTkFrame(frame, fg_color=COLOR_CARD, corner_radius=12)
        card.pack(fill="x", padx=24, pady=0)
        card.grid_columnconfigure(1, weight=1)

        fields = [
            ("GitHub Token", "GITHUB_TOKEN", True),
            ("GitHub Username", "GITHUB_USERNAME", False),
        ]

        import os
        from dotenv import load_dotenv, set_key
        load_dotenv()

        self._setting_entries: dict[str, ctk.CTkEntry] = {}
        for row, (label, key, secret) in enumerate(fields):
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM).grid(row=row, column=0, padx=20, pady=(16 if row == 0 else 8, 8), sticky="w")
            entry = ctk.CTkEntry(card, show="●" if secret else "", font=ctk.CTkFont(size=13),
                                 fg_color="#0d1117", border_color="#2a3a5e", height=38, corner_radius=8)
            entry.insert(0, os.getenv(key, ""))
            entry.grid(row=row, column=1, padx=(0, 20), pady=(16 if row == 0 else 8, 8), sticky="ew")
            self._setting_entries[key] = entry

        ctk.CTkButton(
            card, text="저장",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_ACCENT, hover_color="#3a7ae4",
            height=38, corner_radius=8,
            command=self._save_settings,
        ).grid(row=len(fields), column=0, columnspan=2, padx=20, pady=(8, 20), sticky="ew")

    def _save_settings(self):
        for key, entry in self._setting_entries.items():
            save_env(key, entry.get())
        self._append_log("설정 저장 완료")
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다.")

    # ──────────────────────────────────────────
    # 액션
    # ──────────────────────────────────────────

    def _toggle_watch(self):
        if self._is_watching:
            self._stop_watch()
        else:
            self._start_watch()

    def _start_watch(self):
        projects = load_watch_projects()
        if not projects:
            messagebox.showwarning("알림", "등록된 프로젝트가 없습니다.\n먼저 프로젝트를 추가해주세요.")
            return

        self._watcher_service = WatcherService(log_callback=self._log_queue.put)
        for p in projects:
            self._watcher_service.add_project(p["path"], p["repo_name"], p.get("auto_push", True))

        self._watch_thread = threading.Thread(target=self._watcher_service.start, daemon=True)
        self._watch_thread.start()
        self._is_watching = True

        self._watch_btn.configure(text="■  감시 중지", fg_color=COLOR_DANGER, hover_color="#c62828")
        self._status_badge.configure(text="● 감시 중", text_color=COLOR_SUCCESS)
        self._append_log(f"감시 시작 — {len(projects)}개 프로젝트")
        if self._current_page == "dashboard":
            self._show_page("dashboard")

    def _stop_watch(self):
        if self._watcher_service:
            self._watcher_service.stop()
        self._is_watching = False
        self._watch_btn.configure(text="▶  감시 시작", fg_color=COLOR_ACCENT, hover_color="#3a7ae4")
        self._status_badge.configure(text="● 대기 중", text_color=COLOR_TEXT_DIM)
        self._append_log("감시 중지")
        if self._current_page == "dashboard":
            self._show_page("dashboard")

    def _add_project_dialog(self):
        path = filedialog.askdirectory(title="프로젝트 폴더 선택")
        if not path:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("프로젝트 등록")
        dialog.geometry("420x260")
        dialog.configure(fg_color=COLOR_BG)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="프로젝트 등록", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_TEXT).pack(pady=(24, 4))
        ctk.CTkLabel(dialog, text=path, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM).pack(pady=(0, 16))

        ctk.CTkLabel(dialog, text="GitHub 레포 이름", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=24)
        repo_entry = ctk.CTkEntry(dialog, placeholder_text=Path(path).name,
                                  font=ctk.CTkFont(size=13), fg_color="#0d1117",
                                  border_color="#2a3a5e", height=38, corner_radius=8)
        repo_entry.pack(fill="x", padx=24, pady=(4, 12))

        auto_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(dialog, text="변경 시 자동 push", variable=auto_var,
                        font=ctk.CTkFont(size=13), text_color=COLOR_TEXT).pack(anchor="w", padx=24, pady=(0, 16))

        def confirm():
            repo = repo_entry.get().strip() or Path(path).name
            dialog.destroy()
            self._append_log(f"등록 중: {repo} ...")
            threading.Thread(target=self._do_init_project, args=(path, repo, auto_var.get()), daemon=True).start()

        ctk.CTkButton(dialog, text="등록", font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=COLOR_ACCENT, hover_color="#3a7ae4", height=38, corner_radius=8,
                      command=confirm).pack(fill="x", padx=24, pady=0)

    def _do_init_project(self, path: str, repo: str, auto_push: bool):
        try:
            url = upload_project(path, repo)
            add_watch_project(path, repo, auto_push)
            self._log_queue.put(f"등록 완료: {repo} → {url}")
            self.after(0, lambda: self._show_page(self._current_page))
        except Exception as e:
            self._log_queue.put(f"등록 실패: {e}")

    def _remove_project(self, path: str):
        if messagebox.askyesno("확인", "감시 목록에서 제거할까요?\n(GitHub 레포는 삭제되지 않습니다)"):
            remove_watch_project(path)
            self._show_page("projects")
            self._append_log(f"프로젝트 제거: {path}")

    def _manual_push(self, path: str, repo: str):
        self._append_log(f"수동 push 중: {repo} ...")
        threading.Thread(target=self._do_manual_push, args=(path, repo), daemon=True).start()

    def _do_manual_push(self, path: str, repo: str):
        try:
            update_project(path, repo, push=True)
            self._log_queue.put(f"push 완료: {repo}")
        except Exception as e:
            self._log_queue.put(f"push 실패: {e}")

    # ──────────────────────────────────────────
    # 헬퍼
    # ──────────────────────────────────────────

    def _make_page_frame(self, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._content, fg_color=COLOR_BG, corner_radius=0)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=20, weight="bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=28, pady=(28, 16))
        return frame


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
