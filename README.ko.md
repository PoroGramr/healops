# HealOps

Docker 기반 장애 감시 및 복구 플랫폼 MVP입니다. Kubernetes 어댑터는 추후 개발합니다. [English](README.md)

현재 초기 개발 단계입니다. 기본 동작은 읽기 전용이며 자동 배포하지 않습니다. API/웹에는 Docker 소켓을 연결하지 않고 명시적으로 등록한 데모 컨테이너만 별도 작업자가 처리합니다. Docker 소켓 자체는 호스트 수준 권한이므로 운영 Docker 데몬에서 실행하지 마세요.

실행 및 테스트 방법은 [배포 문서](docs/deployment.md), 보안 모델은 [보안 문서](docs/security.md)를 참고하세요. 기여 전 이슈를 열고 테스트를 실행해 주세요. 라이선스는 Apache-2.0입니다.
