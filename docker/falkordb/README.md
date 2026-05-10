# docker/falkordb

camfit 지식그래프 적재용 FalkorDB. 공식 이미지 사용.

## WSL 에서 부팅

```bash
cd /mnt/d/github/cf/docker/falkordb
docker compose up -d
docker compose ps
```

## 노출

- `localhost:6379` — Redis 프로토콜 (Cypher via `GRAPH.QUERY`)
- `localhost:3000` — FalkorDB Browser UI (브라우저로 그래프 조회)

## 접속 확인

```bash
docker exec -it camfit-falkordb redis-cli ping
# PONG

# 그래프 카운트
docker exec -it camfit-falkordb redis-cli GRAPH.QUERY camfit "MATCH (n) RETURN count(n)"
```

## 정지/삭제

```bash
docker compose down          # 컨테이너만
docker compose down -v       # 데이터 볼륨까지 삭제 (graph reset)
```
