# GitHub Auto Upload

VSCode 작업물을 GitHub에 자동으로 커밋/푸시하고 업데이트를 관리하는 툴입니다.

## 주요 기능

- **자동 감시** — 프로젝트 폴더를 실시간으로 감시하다가 파일이 변경되면 자동으로 커밋 & 푸시
- **커밋 메시지 자동 생성** — 변경된 파일 이름과 개수를 기반으로 커밋 메시지를 자동으로 만들어줌
- **GUI 인터페이스** — 계정 연동 상태, 등록된 프로젝트, 활동 로그를 한눈에 확인
- **CLI 지원** — 터미널에서도 동일한 기능 사용 가능
- **VSCode 연동** — `tasks.json` 자동 생성으로 단축키 한 번에 push 가능

## 스크린샷

> 대시보드 / 프로젝트 관리 / 활동 로그 / 설정 탭으로 구성된 다크 테마 GUI

## 설치 방법

### 방법 1 — exe 실행 (권장)

1. [Releases](https://github.com/simmarine/github_auto_upload/releases/latest) 에서 `GitHubAutoUpload.exe` 다운로드
2. exe 파일과 같은 폴더에 `.env` 파일 생성

```env
GITHUB_TOKEN=your_token_here
GITHUB_USERNAME=your_username
```

3. `GitHubAutoUpload.exe` 실행

### 방법 2 — 소스 실행

```bash
git clone https://github.com/simmarine/github_auto_upload.git
cd github_auto_upload

pip install -r requirements.txt

cp .env.example .env
# .env 파일에 토큰과 유저명 입력

python gui.py       # GUI 실행
python main.py --help  # CLI 실행
```

## GitHub Token 발급

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. `repo` 권한 체크 후 생성
3. 발급된 토큰을 `.env`의 `GITHUB_TOKEN`에 입력

## GUI 사용법

| 탭 | 기능 |
|---|---|
| 대시보드 | 계정 연동 상태 확인, 등록 프로젝트 요약 |
| 프로젝트 | 폴더 선택 → GitHub 레포 자동 생성 및 등록 |
| 활동 로그 | 커밋/푸시 이력 실시간 확인 |
| 설정 | GitHub Token / Username 저장 |

사이드바 하단 **▶ 감시 시작** 버튼을 누르면 등록된 모든 프로젝트를 자동 감시합니다.

## CLI 사용법

```bash
# 프로젝트 GitHub에 등록 + 초기 업로드
python main.py init ./my-project

# 파일 감시 시작 (변경 감지 시 자동 push)
python main.py watch

# 수동 업로드 / 업데이트
python main.py upload ./my-project

# 등록된 프로젝트 목록 확인
python main.py list-projects

# VSCode tasks.json 자동 생성
python main.py vscode-setup ./my-project
```

## 기술 스택

| 항목 | 내용 |
|---|---|
| Language | Python 3.11 |
| GUI | customtkinter |
| CLI | typer |
| 파일 감시 | watchdog |
| GitHub API | requests |
| 패키징 | PyInstaller |

## 프로젝트 구조

```
github_auto_upload/
├── gui.py                  # GUI 진입점
├── main.py                 # CLI 진입점
├── src/
│   ├── config.py           # 설정 관리, 프로젝트 목록
│   ├── github_manager.py   # GitHub 레포 생성 / 업로드 / 업데이트
│   └── watcher.py          # 파일 변경 감지 → 자동 커밋/푸시
├── config/
│   └── watch_projects.json # 감시 프로젝트 목록 (런타임 생성)
├── .env.example            # 환경변수 예시
└── requirements.txt
```

## 주의사항

- `.env` 파일에는 GitHub 토큰이 포함되므로 **절대 공유하거나 커밋하지 마세요**
- 토큰은 `repo` 스코프 최소 권한만 부여하는 것을 권장합니다

## License

MIT
