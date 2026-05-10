# docker/

WSL Docker 로 두 DB 를 동시에 부팅하는 umbrella + 개별 compose.

## 한 번에 부팅 (권장)

WSL 쉘에서:

```bash
cd /mnt/d/github/cf/docker
docker compose up -d --build
docker compose ps
```

| 서비스 | 포트 | 설명 |
|-------|------|------|
| `camfit-falkordb` | 6379 (cypher), 3000 (browser UI) | KG 적재/쿼리 |
| `camfit-rocksdb` | 8071 (HTTP) | row 적재/scan |

## 개별 부팅

- `docker/falkordb/` — FalkorDB 단독
- `docker/rocksdb/` — RocksDB HTTP 서비스 단독

## 정지

```bash
docker compose stop          # 일시 정지
docker compose down          # 컨테이너 삭제 (볼륨 유지)
docker compose down -v       # 데이터까지 초기화
```

## Windows 호스트에서 접속

WSL 의 docker 가 `localhost:6379` `localhost:8071` `localhost:3000` 에 바인드되면 Windows 호스트도 동일 주소로 접속 가능 (WSL2 가 자동 forwarding).
