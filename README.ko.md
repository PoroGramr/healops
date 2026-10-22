# HealOps

Docker 컨테이너 장애를 감시하고 원인을 분석해 **관리자 승인 기반 재시작**을 제공하는 오픈소스 MVP입니다. Kubernetes는 미구현 로드맵입니다. [English](README.md)

> **실험용:** 일반 데모 작업자의 직접 Docker 소켓 연결은 운영 서버에서 사용하면 안 됩니다. 운영 감시는 읽기 전용 프록시와 단일 서비스 실행자를 분리했지만, 실행자의 소켓은 여전히 호스트 수준 권한입니다. 대시보드는 로컬 주소에만 바인딩됩니다.

공유 서버에서 PW3를 상시 감시하려면 [상시 감시 문서](docs/continuous-monitor.md)를 참고하세요. 별도 복구 오버레이는 단일 서비스의 제한된 자동 재시작과 HTTP 검증을 제공합니다. 자동 코드 패치·배포는 아직 없습니다.

## 구현된 기능

- 등록한 컨테이너의 Docker Events 구독 및 5초 주기 상태·종료 코드·헬스체크·로그 확인, 중복 장애를 SQLite에 기록
- LangGraph 진단 서브그래프, 규칙 기반 기본 진단, 선택적 OpenAI 호환 LLM 진단
- 실제 API 데이터를 표시하는 React/Vite 다크 대시보드 및 승인 화면
- 별도 작업자와 관리자 인증, 승인과 기본 비활성화된 재시작 스위치를 모두 거쳐 Docker 재시작
- Alembic 스키마, 장애 재현용 예제, Python/프론트엔드 테스트, CI

HealOps 내부의 무인 코드 수정·실제 복구 PR 발행/병합·운영 배포·DB 롤백·Kubernetes는 **아직 동작하지 않습니다**. [Codex 작업 트리 어댑터](docs/patch-proposals.md)는 분리된 PW3 복제본의 실패하는 Java 테스트를 고치고 격리 테스트와 스테이징 배포를 통과했지만, 운영 장애에는 연결하지 않았습니다. PW3의 별도 Actions 배포 스크립트는 이미지·환경·Compose 설정의 실패 시 복원을 갖췄습니다. [로드맵](docs/roadmap.md).

PW3 운영 데이터와 분리된 MySQL·MinIO [스테이징 및 이미지 롤백 검증](docs/pw3-staging.md)은 운영 자동 배포와 별개입니다.

## 로컬 실행

```bash
git clone https://github.com/PoroGramr/healops.git && cd healops
cp .env.example .env && chmod 600 .env
# .env의 HEALOPS_API_TOKEN, HEALOPS_WORKER_TOKEN을 각각 다른 무작위 비밀값으로 교체
docker compose -f deploy/docker-compose.yml up -d --build
```

`http://127.0.0.1:8088`에서 관리자 토큰을 입력합니다. 외부 인터넷에 공개하지 마세요. `curl http://127.0.0.1:8099/break`로 오류를 만들고 잠시 후 대시보드에서 장애를 확인합니다. `curl http://127.0.0.1:8099/reset`으로 복구합니다. 기본 구성에서는 재시작하지 않습니다.

테스트·LLM 설정은 [배포 문서](docs/deployment.md), 권한 위험은 [보안 문서](docs/security.md)를 참고하세요. 기여 전 이슈를 열고 테스트를 추가해 주세요. Apache-2.0 라이선스입니다.
