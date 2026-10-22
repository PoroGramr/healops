# HealOps

Docker 컨테이너 장애를 감시하고 원인을 분석해 **관리자 승인 기반 재시작**을 제공하는 오픈소스 MVP입니다. Kubernetes는 미구현 로드맵입니다. [English](README.md)

> **실험용:** Docker 소켓은 호스트 수준 권한입니다. 작업자 코드의 컨테이너 허용 목록만으로는 보안 경계가 되지 않습니다. 운영 컨테이너가 있는 Docker 데몬에 연결하지 말고 별도 테스트 VM/데몬에서만 실행하세요. 웹은 로컬 주소에만 바인딩되며 기본값은 읽기 전용입니다.

## 구현된 기능

- 등록한 컨테이너의 상태·종료 코드·헬스체크·최근 로그를 5초마다 확인하고 중복 장애를 SQLite에 기록
- LangGraph 진단 서브그래프, 규칙 기반 기본 진단, 선택적 OpenAI 호환 LLM 진단
- 실제 API 데이터를 표시하는 React/Vite 다크 대시보드 및 승인 화면
- 별도 작업자와 관리자 인증, 승인과 기본 비활성화된 재시작 스위치를 모두 거쳐 Docker 재시작
- Alembic 스키마, 장애 재현용 예제, Python/프론트엔드 테스트, CI

Docker Events 스트림, 메트릭, Codex 코드 패치, PR 생성, 운영 배포, 롤백, 자동 재시도/서킷 브레이커, Kubernetes는 **아직 구현되지 않았습니다**. [로드맵](docs/roadmap.md).

## 로컬 실행

```bash
git clone https://github.com/PoroGramr/healops.git && cd healops
cp .env.example .env && chmod 600 .env
# .env의 HEALOPS_API_TOKEN, HEALOPS_WORKER_TOKEN을 각각 다른 무작위 비밀값으로 교체
docker compose -f deploy/docker-compose.yml up -d --build
```

`http://127.0.0.1:8088`에서 관리자 토큰을 입력합니다. 외부 인터넷에 공개하지 마세요. `curl http://127.0.0.1:8099/break`로 오류를 만들고 잠시 후 대시보드에서 장애를 확인합니다. `curl http://127.0.0.1:8099/reset`으로 복구합니다. 기본 구성에서는 재시작하지 않습니다.

테스트·LLM 설정은 [배포 문서](docs/deployment.md), 권한 위험은 [보안 문서](docs/security.md)를 참고하세요. 기여 전 이슈를 열고 테스트를 추가해 주세요. Apache-2.0 라이선스입니다.
