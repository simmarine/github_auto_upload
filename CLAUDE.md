# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

VSCode 작업물을 GitHub에 자동으로 커밋/푸시하고 업데이트를 관리하는 툴.
GUI(customtkinter)와 CLI(typer) 두 가지 인터페이스를 제공한다.

## 실행 명령어

```bash
# 환경 설정
pip install -r requirements.txt

# GUI 실행
python gui.py

# CLI 사용
python main.py init <프로젝트경로>        # 프로젝트 GitHub 등록
python main.py watch                      # 파일 감시 시작 (자동 push)
python main.py upload <프로젝트경로>      # 수동 업로드/업데이트
python main.py list-projects              # 등록 목록 조회
python main.py vscode-setup <경로>        # VSCode tasks.json 생성
```

## 아키텍처

```
gui.py                     # GUI 진입점 (customtkinter)
main.py                    # CLI 진입점 (typer)
src/
  config.py               # 설정 관리, 감시 프로젝트 목록 (watch_projects.json)
  github_manager.py       # GitHub 레포 생성, 초기 업로드, 업데이트
  watcher.py              # watchdog 기반 파일 변경 감지 → 자동 commit/push
config/
  watch_projects.json     # 감시 중인 프로젝트 목록 (런타임 생성)
```

**핵심 흐름:**
1. `init` → `github_manager.upload_project()` → GitHub 레포 생성 + 초기 push
2. `watch` → `WatcherService` → 파일 변경 감지 (debounce 5초)
3. 변경 감지 → 커밋 메시지 자동 생성 → `github_manager.update_project()` → push

## 환경변수 (.env)

```
GITHUB_TOKEN=          # GitHub Personal Access Token (repo scope)
GITHUB_USERNAME=       # GitHub 유저명
```

## 규칙

- `.env` 파일 절대 수정/커밋 금지
- GitHub 토큰은 최소 권한(repo scope)만 사용
- `config/watch_projects.json`이 감시 프로젝트 목록의 단일 진실 소스
- GUI와 CLI는 동일한 src/ 모듈을 공유
