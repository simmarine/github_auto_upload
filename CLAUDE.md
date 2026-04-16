# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

GitHub 자동 업로드 + Tistory 카테고리별 자동 포스팅 자동화 도구.
작업 결과물을 GitHub에 커밋/푸시하고, 동시에 Tistory 블로그에 카테고리별로 정리해서 발행한다.

## 실행 명령어

```bash
# 환경 설정
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 실행
python main.py upload --file 파일경로 --category 카테고리명
python main.py upload --dir 폴더경로 --category 카테고리명

# 카테고리 목록 조회
python main.py categories

# 테스트
pytest tests/
pytest tests/test_github.py  # 단일 테스트

# 포맷
black src/ tests/
```

## 아키텍처

```
main.py                    # CLI 진입점 (typer 기반)
src/
  config.py               # .env 로드, 설정값 관리
  github_manager.py       # git commit/push, GitHub API
  tistory_manager.py      # Tistory OAuth2 인증, 글 작성/수정 API
  content_converter.py    # Markdown → HTML 변환, 코드 하이라이팅
  category_manager.py     # Tistory 카테고리 조회 및 로컬 매핑
config/
  categories.yaml         # 로컬 폴더명 ↔ Tistory 카테고리 ID 매핑
templates/
  post_template.html      # Tistory 포스트 HTML 템플릿
```

**핵심 흐름:**
1. `main.py` → `github_manager`로 커밋/푸시
2. `content_converter`로 마크다운 → HTML 변환
3. `category_manager`로 카테고리 ID 조회
4. `tistory_manager`로 포스트 작성

## 환경변수 (.env)

```
GITHUB_TOKEN=          # GitHub Personal Access Token
GITHUB_REPO=           # owner/repo 형식
TISTORY_APP_KEY=       # Tistory 앱 키
TISTORY_SECRET_KEY=    # Tistory 시크릿 키
TISTORY_BLOG_NAME=     # 블로그 이름 (xxx.tistory.com의 xxx)
TISTORY_ACCESS_TOKEN=  # OAuth 인증 후 저장되는 토큰
```

## 규칙

- `.env` 파일 절대 수정/커밋 금지
- Tistory API는 HTML만 허용 — content_converter 거치지 않고 직접 전달 금지
- GitHub 토큰은 최소 권한(repo scope)만 사용
- `config/categories.yaml`이 로컬 카테고리명과 Tistory ID의 단일 진실 소스
