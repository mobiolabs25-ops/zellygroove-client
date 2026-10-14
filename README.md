<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-on-dark.svg">
    <img src="assets/logo.svg" alt="Zelly Groove" width="340">
  </picture>
</p>

# Zelly Groove Client

[Zelly Groove](https://zellygroove.com)의 일반 사용자용 **MCP · CLI · AI 스킬**입니다.
Claude Code, Codex와 함께 음악을 만들고, 작업 상태와 남은 크레딧을 확인하세요.

## 빠른 시작

Python 3.11–3.12, Git, [uv](https://docs.astral.sh/uv/getting-started/installation/)가 필요합니다.

```sh
uv tool install --python 3.11 --from git+https://github.com/mobiolabs25-ops/zellygroove-client@v0.1.0 zellygroove-client
zellygroove login
zellygroove setup --client auto
```

`login`은 [설정 → 연결](https://zellygroove.com/ui/#/settings/connect)에서 발급한 본인 토큰을 숨김 입력으로 받습니다.
`setup`은 설치된 Claude Code·Codex CLI에 MCP와 스킬을 등록합니다. 하나만 연결하려면 `--client claude` 또는 `--client codex`를 사용하세요.
에이전트를 다시 시작한 뒤 **“Zelly Groove의 남은 크레딧을 확인해 줘”**라고 요청하면 됩니다.

## CLI

```sh
zellygroove                         # 지원 도구 목록
zellygroove studio_usage            # 이용 한도와 사용량
zellygroove studio_credits          # 지급·예약·사용·잔여 크레딧
zellygroove list_models             # 모델 선택지와 후보당 크레딧
zellygroove list_jobs               # 최근 작업
zellygroove create_song artist_id=null instrumental=true prompt="따뜻한 피아노"
zellygroove get_job job_id=<반환된_ID>
```

곡·가사·재킷·영상·앨범·플레이리스트·BGM 생성과 결과 관리, 허용된 Wiki 조회를 지원합니다.
`get_job`은 재조회이고, **`retry_job`은 새 생성**이므로 한도·크레딧이 다시 적용됩니다.
호출 제한(429)을 받으면 안내된 대기 시간 뒤에 조회하세요. 클라이언트는 자동으로 재시도하지 않습니다.
MIDI·허밍 업로드, 고급 편집, 다운로드와 결제 관리는 웹 스튜디오를 이용하세요.

## AI 에이전트용 연결 절차

**사용자가 이 README 링크와 함께 연동을 요청하면 다음 순서로 실행하세요.**

1. `uv`, `git`, `claude`, `codex` 설치 여부를 확인합니다. 사용자가 지정한 클라이언트를 우선하고, 지정하지 않으면 설치된 클라이언트를 선택합니다. 빠진 프로그램은 공식 설치 안내에 따라 준비합니다.
2. 위 `uv tool install` 명령으로 고정 버전 `v0.1.0`을 설치합니다. `uv tool update-shell`이 필요하면 안내하고, 현재 실행에서는 `uv tool dir --bin`으로 실행 파일 위치를 확인합니다.
3. `zellygroove setup --client claude|codex|auto`를 실행합니다. 기존 Zelly Groove/Mobio Studio 연결은 자동 덮어쓰지 않습니다. 기존 설정이 있다면 그 항목만 검토하며 다른 MCP 설정은 보존합니다.
4. **토큰을 채팅으로 요청하거나 출력하지 마세요.** 저장된 토큰이 없다면 사용자에게 본인 터미널에서 `zellygroove login`을 한 번 실행하도록 안내합니다. 로그인 웹 화면과 토큰 발급은 사용자 인증이 필요합니다.
5. `zellygroove studio_status`, `zellygroove studio_usage`, `zellygroove studio_credits`로 확인합니다. 401·403이면 서비스가 반환한 인증·권한 오류를 보고하며, 다른 자격증명으로 우회하지 않습니다. 아직 운영 서버에 반영되지 않은 기능은 설치 성공과 구분합니다.
6. MCP 등록과 API 연결을 각각 보고하고 에이전트 재시작을 안내합니다. 연결 시험만을 위해 곡을 생성하지 마세요. 재시작 후 MCP의 `studio_credits`를 호출하면 최종 확인할 수 있습니다.

Claude Code·Codex CLI 외의 stdio MCP 클라이언트에서는 다음처럼 등록합니다. 실행 파일과 토큰 파일의 절대 경로는 사용자 환경에 맞게 바꾸세요.

```json
{
  "mcpServers": {
    "zellygroove": {
      "command": "/absolute/path/to/zellygroove-mcp",
      "env": {
        "STUDIO_URL": "https://zellygroove.com",
        "STUDIO_TOKEN_FILE": "/absolute/path/to/.config/zellygroove/token.json"
      }
    }
  }
}
```

스킬만 설치하려면 `zellygroove install-skill claude` 또는 `zellygroove install-skill codex`를 사용합니다.

## 권한과 보안

웹·MCP·CLI는 **같은 계정의 크레딧·한도·다운로드 권한**을 사용합니다. 실제 제공 기능은 서비스의 현재 요금제와 권한을 따릅니다.
이 저장소에는 운영진 도구, 서비스 서버 코드, 모델 가중치, 운영 설정이 포함되지 않습니다.
토큰은 서비스 주소에 묶어 로컬 파일에 저장하며, POSIX에서는 본인 소유 `0600` 파일만 읽습니다. 환경 변수 `STUDIO_TOKEN`도 지원하지만 출력·커밋하지 마세요.
보안 문제를 발견하면 토큰이나 개인정보를 공개 이슈에 올리지 말고 [서비스 문의](https://zellygroove.com)로 알려 주세요.

코드: [MIT](LICENSE). 로고·서비스명: [브랜드 사용 안내](assets/NOTICE.md).
