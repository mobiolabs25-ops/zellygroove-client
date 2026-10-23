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
uv tool install --python 3.11 --from git+https://github.com/mobiolabs25-ops/zellygroove-client@v0.3.1 zellygroove-client
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
추가 기능은 `studio_capabilities`로 입력 형식을 확인하고 `studio_action`으로 실행합니다. 파일 리소스는 인증된 다운로드 주소로, 로그인·결제사 인증처럼 화면이 필요한 단계는 해당 웹 화면으로 연결합니다.

## 아티스트와 대화하기 (Groovy Pro)

기능 조회를 지원하는 기존 일반 MCP 연결(v0.3.0 이상)에서도 아티스트와 대화할 수 있습니다.
`studio_capabilities`로 대화 기능을 확인하고 `studio_action`으로 외부 모델 세션을 열면 됩니다.
아래 전용 연결은 아티스트와 도구 범위를 고정하는 선택 사항입니다. 두 방식 모두 Groovy Pro와 해당 아티스트 접근 권한이 필요합니다.

공개 HTTPS API에 **본인 PAT**로 연결합니다. SSH 터널이나 서버 운영 계정은 필요하지 않습니다.
`list_artists`에서 접근 가능한 아티스트 ID를 확인하고 전용 연결을 등록하세요.

```sh
zellygroove setup --client codex --artist ines_vauclair
# Claude Code: --client claude
```

기존 일반 연결을 보존하고 `zellygroove_ines_vauclair`라는 별도 연결에 `STUDIO_ARTIST_ID`를 설정합니다.
에이전트를 다시 시작한 뒤 “Inès와 대화하자”라고 말하면 됩니다. 직접 등록하는 경우 위 MCP 환경에
`STUDIO_ARTIST_ID=ines_vauclair`를 추가합니다. CLI도 이 변수가 있으면 같은 아티스트 도구만 제공합니다.

- Claude/Codex의 현재 대화 모델이 페르소나와 이력을 읽고 답합니다. 로컬 모델을 별도로 내려받는 기능은 아닙니다.
- 대화는 `Inès >`처럼 표시하고 실제 사용자 메시지와 답변을 서버의 개인 이력에 저장합니다. 웹에서도 이어볼 수 있습니다.
- 현재 대화 컨텍스트가 허용하는 도구로 해당 아티스트의 실제 곡을 조회하고 추천하거나, 가사·악기·스타일을 함께 설계합니다.
- 완성된 초안을 검토하고 사용자가 음원 생성을 요청하면 생성합니다. 대화 초안을 저장하는 것만으로 음원을 만들지 않습니다.
- 외부 모델 대화의 Studio 대화 크레딧은 0이며, Claude/Codex 자체 이용료와 음원 생성 크레딧은 별도입니다.
- 기억은 요청할 때 개인 저장소에 저장·수정·삭제합니다. 공유·공개 범위 변경은 내용을 확인한 뒤 일반 연결의 `studio_action` 또는 Wiki 화면에서 진행합니다.
- Free/Groovy의 웹 Zelly 대화와 별개로, 아티스트 대화·기억·전용 MCP는 Groovy Pro와 해당 아티스트 접근 권한이 필요합니다.

`STUDIO_ARTIST_ID`는 이 MCP 연결의 도구 범위를 고정합니다. **PAT 자체를 특정 아티스트에 한정하는 토큰 scope는 아닙니다.**
최종 접근 제어는 API가 PAT 소유자의 구독·멤버십·대화 소유권으로 검사합니다. 공유 대화에서도 개인 이력은 다른 사용자에게 공개되지 않습니다.
쓰기 요청은 요청 ID로 중복 저장을 막고, 이력 변경 충돌은 409, 호출 한도는 429로 반환합니다.

### 이전 버전에서 업데이트

```sh
uv tool install --force --python 3.11 --from git+https://github.com/mobiolabs25-ops/zellygroove-client@v0.3.1 zellygroove-client
```

CLI 설치와 MCP 등록은 별개입니다. 기존 일반 연결과 아티스트 전용 연결의 `--from`에 이전 버전이
고정돼 있으면 해당 Zelly Groove 항목만 `@v0.3.1`로 갱신하세요. 다른 MCP 설정과 저장된 토큰 파일은 보존합니다.
`setup`은 기존 연결을 자동 덮어쓰지 않고, 설치된 스킬 내용이 다르면 중단합니다.
수정한 스킬을 별도로 보관한 뒤 새 `zellygroove guide`의 아티스트 실행 절차를 반영하세요.
CLI와 MCP 등록, 스킬을 모두 갱신한 뒤 Claude/Codex를 다시 시작해야 초기 안내와 도구 설명이 다시 로드됩니다.
토큰을 새로 발급할 필요는 없으며, 기존 유효한 PAT를 그대로 사용할 수 있습니다.

### Claude/Codex가 대화를 진행하는 방식

아티스트 대화는 **문맥 읽기 → 필요한 자료 조회 → 결과 확인 → 답변 작성 → 저장 확인** 순서로 진행합니다.
각 사용자 턴에서 서버의 `read_artist_conversation`을 읽으며, 서버가 제공하는 `execution_guide`와
현재 도구·답변 스키마를 따릅니다. 추가 조회는 기본 최대 두 묶음(묶음마다 최대 세 도구)으로 안내합니다.
이는 클라이언트 행동 지침이며 서버가 모델 호출 횟수를 강제한다는 뜻은 아닙니다.

- “네 곡 중 몇 곡 추천해 줘”: 연결한 아티스트의 실제 곡을 확인하고 그 ID·제목만 추천합니다.
- “하나 들려줘”: 직전 추천에서 한 곡을 선택합니다. 재생 링크가 제공되면 안내하고, ID·제목만 있으면
  해당 곡을 웹 스튜디오에서 열도록 안내합니다. 재생을 확인하지 않고 “재생 중”이라고 말하지 않습니다.
- “그래”: 직전의 구체적인 제안을 이어갑니다. 기존 곡 듣기를 새 음원 생성으로 바꾸지 않습니다.
- 가사·초안: 사용자 원문을 보존하고 저장 결과를 확인합니다. 음원 생성과 기억 저장은 사용자 요청이 있을 때 진행합니다.

상세 실행 절차와 재전송·충돌·권한·검증 오류 대응은 [아티스트 대화 가이드](docs/artist-conversation-guide.md)를 참고하세요.
현재 안내에는 서버의 자동 1회 보완 루프 구현이 포함되지 않습니다. 이 정책은 서버가 명시적으로 제공할 때만 적용합니다.

## AI 에이전트용 연결 절차

**사용자가 이 README 링크와 함께 연동을 요청하면 다음 순서로 실행하세요.**

1. `uv`, `git`, `claude`, `codex` 설치 여부를 확인합니다. 사용자가 지정한 클라이언트를 우선하고, 지정하지 않으면 설치된 클라이언트를 선택합니다. 빠진 프로그램은 공식 설치 안내에 따라 준비합니다.
2. 위 `uv tool install` 명령으로 고정 버전 `v0.3.1`을 설치합니다. `uv tool update-shell`이 필요하면 안내하고, 현재 실행에서는 `uv tool dir --bin`으로 실행 파일 위치를 확인합니다.
3. `zellygroove setup --client claude|codex|auto`를 실행합니다. 기존 Zelly Groove/Mobio Studio 연결은 자동 덮어쓰지 않습니다. 기존 설정이 있다면 그 항목만 검토하며 다른 MCP 설정은 보존합니다.
4. **토큰을 채팅으로 요청하거나 출력하지 마세요.** 저장된 토큰이 없다면 사용자에게 본인 터미널에서 `zellygroove login`을 한 번 실행하도록 안내합니다. 로그인 웹 화면과 토큰 발급은 사용자 인증이 필요합니다.
5. 일반 연결에서는 `zellygroove studio_status`, `zellygroove studio_usage`, `zellygroove studio_credits`로 확인합니다. 401·403이면 서비스가 반환한 인증·권한 오류를 보고하며, 다른 자격증명으로 우회하지 않습니다. 아직 운영 서버에 반영되지 않은 기능은 설치 성공과 구분합니다.
6. 아티스트 연결은 일반 도구가 노출되지 않습니다. 사용자 요청에 따라 `open_artist_conversation`과 `read_artist_conversation`으로 페르소나·현재 허용 도구를 확인하세요. 일반 연결 시험을 아티스트 연결에 요구하지 마세요.
7. MCP 등록과 API 연결을 각각 보고하고 에이전트 재시작을 안내합니다. 연결 시험만을 위해 곡을 생성하지 마세요. 재시작 후 일반 연결의 `studio_credits` 또는 아티스트 연결의 `read_artist_conversation`으로 최종 확인할 수 있습니다.

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


### 완성 음원 미리듣기 링크 (v0.2.1)

생성 요청 시 `share_preview=true`를 선택하면 완성 뒤 1시간 동안 로그인 없이 들을 수 있는 링크가 준비됩니다.
즉시 반환되는 `job_url`로 작업을 열거나, `read_conversation_song`으로 `preview_url`과 만료 시각을 확인하세요.
`share_lounge=true`는 별도 선택이며 아티스트 소유권과 재킷 조건을 검사합니다. 조회는 공유를 시작하거나 갱신하지 않습니다.
서버의 `/api/song-agent/sessions/{id}/result` 지원과 함께 사용해야 합니다.

## v0.3.0 기능 확장

기존 도구와 로그인·설정 명령을 유지하고 사용자용 도구70개를 제공합니다.

- 기능 검색·상세 입력 조회·고정 작업 실행: `studio_capabilities`, `studio_action`
- 요청 내 중복 조회를 합치는 읽기 배치: `studio_read_batch`
- Pro Wiki3D 제어: `list_musician_wiki_tabs`, `send_musician_wiki_command`, `get_musician_wiki_command_status`
- 작업 후보별 미리듣기, 이미지·영상 모델, 곡별 이용 조건, 새 버전·편곡·원본 보컬 활용
- 아티스트 대화의 다곡 결과와 모델·길이·박자 선택 전달

Wiki는 Groovy Pro와 운영자 권한을 따르며 일반 MCP 연결은 모든 현재 요금제에서 이용할 수 있습니다. 새로운 도구는 대응 서버 배포 후 사용할 수 있습니다. 삭제·권한·결제·외부 게시 변경은 정확한 내용 확인 후 실행하고, 브라우저 인증이 필요한 단계는 화면 링크로 이어집니다. `queued`는 Wiki 화면 적용 완료가 아닙니다.

```sh
zellygroove studio_capabilities query=scores
zellygroove studio_action operation_id=get.scores 'arguments={"query":{"paged":true,"limit":20}}'
zellygroove list_musician_wiki_tabs artist_id=ines_vauclair
```

서버 비공개 코드·운영 설정·사용자 자료는 이 배포본에 포함하지 않습니다.
