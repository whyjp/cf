# 그래프 데이터 모델 리팩토링 — Region → Attribute → Camp

> 본 문서는 **임베딩/노드 적재 리팩토링** 을 진행하는 에이전트를 위한 요구 사양입니다. FE 그래프 뷰 (`fe/graph.html`) 가 의도대로 시각적 의미를 전달하려면 KG 모델을 아래와 같이 바꿔야 합니다.

## 현재 (As-is)

```
(Camp) -[:LOCATED_IN]-> (Region)
(Camp) -[:HAS_CATEGORY]-> (Category)
(Camp) -[:HAS_FACILITY]-> (Facility)
```

- **모든 엣지가 Camp 에서 시작.**
- Region/Category/Facility 는 *terminal* 속성 노드. 자기들끼리는 연결 없음.
- 결과적으로 그래프가 *Camp-centric*: Camp 1개당 평균 3 엣지가 사방으로 뻗어 별모양 형성.
- 사용자 멘탈 모델 (지역으로 시작 → 그 지역의 속성 → 그 속성을 갖는 캠프) 과 어긋남.

## 목표 (To-be)

```
(Region) -[:HAS_ATTRIBUTE]-> (RegionAttribute) -[:CAMP]-> (Camp)
```

순차 토폴로지: **지역 → 속성 → 캠핑장**.

여기서 `RegionAttribute` 는 *지역+속성* 의 조합으로 인스턴스가 생기는 노드. 예:

| Region | RegionAttribute (Category 계열) | RegionAttribute (Facility 계열) |
|---|---|---|
| `(강원,평창군)` | `(강원,평창군,계곡)` | `(강원,평창군,트램펄린)` |
| `(경기,가평군)` | `(경기,가평군,키즈캠핑)` | `(경기,가평군,온라인결제)` |

각 RegionAttribute 노드는 *해당 지역에서 그 속성을 가진 Camp 들* 만 가리킨다. → 한 Camp 가 N 개 카테고리 + M 개 시설을 갖고 있다면 N+M 개의 RegionAttribute 노드에 연결된다.

## 왜 이렇게?

1. **지역 우선 탐색** — Region 노드를 anchor 로 하면 사용자가 "강원 평창군 → 계곡 → 어떤 캠프가 있나" 흐름으로 자연스럽게 drill-down 가능.
2. **속성 클러스터링** — 같은 지역+속성 캠프들이 한 노드 아래 묶임 → 그래프 뷰에서 자연스러운 *클러스터* 가 보임.
3. **필터링 단순화** — `(Region {sido:'강원'})-[:HAS_ATTRIBUTE]->(:RegionAttribute {kind:'Category', name:'계곡'})-[:CAMP]->(c)` 한 cypher 로 "강원 계곡 캠프" 가 즉시 답.
4. **시각적 수렴** — 그래프에서 Camp 가 잎(leaf), Attribute 가 중간 hub, Region 이 root 인 트리에 가까운 구조 → 인지 부하가 낮아짐.

## 구체 노드/엣지 정의

### 노드

```
(:Region {
   sido: string,
   sigungu: string,
   id: "Region:{sido}|{sigungu}"   // synthetic, optional
})

(:RegionAttribute {
   id: "RA:{sido}|{sigungu}|{kind}|{name}",
   kind: "Category" | "Facility",
   name: string,                  // 예: "계곡", "트램펄린"
   sido: string,
   sigungu: string,
   camp_count: int                // (선택) 미리 계산된 캠프 수, 시각화용
})

(:Camp { ... 기존 그대로 ... })
```

### 엣지

```
(:Region) -[:HAS_ATTRIBUTE]-> (:RegionAttribute)
(:RegionAttribute) -[:CAMP]-> (:Camp)

# 호환성 유지가 필요하면 기존 엣지를 (deprecated 표시 후) 동시 유지 가능:
(:Camp) -[:LEGACY_LOCATED_IN]-> (:Region)   # 점진 폐지 대상
(:Camp) -[:LEGACY_HAS_CATEGORY]-> (:Category)
(:Camp) -[:LEGACY_HAS_FACILITY]-> (:Facility)
```

> 구 `Category`/`Facility` 노드는 *전역* 속성을 표현 (지역 무관). 새 모델은 *지역-종속* 속성으로 대체한다. 두 노드 타입을 어떻게 처리할지는 마이그레이션 정책에 따라 결정 (병행 vs 폐지).

## 적재 (`camfit-puller load-falkor`) 변경점

`src/camfit_puller/kg_builder.py` 의 `build()` 함수가 현재 한 Camp 당 1 statement 를 생성. 이를 다음으로 확장:

```python
# 의사 코드
for rec in records:
    sido, sigungu = rec.region_sido, rec.region_sigungu

    # 1. Region MERGE (기존)
    yield CypherStmt(
        "MERGE (r:Region {sido: $sido, sigungu: $sigungu})",
        {"sido": sido, "sigungu": sigungu},
    )

    # 2. Camp MERGE (기존, 단 LOCATED_IN 엣지는 더 이상 직접 만들지 않음)
    yield CypherStmt(
        "MERGE (c:Camp {id: $id}) SET c.name=$name, ...",
        {...},
    )

    # 3. 카테고리 → RegionAttribute → Camp
    for cat in rec.categories:
        yield CypherStmt(
            "MATCH (r:Region {sido:$sido, sigungu:$sigungu}) "
            "MERGE (ra:RegionAttribute {sido:$sido, sigungu:$sigungu, kind:'Category', name:$name}) "
            "MERGE (r)-[:HAS_ATTRIBUTE]->(ra) "
            "WITH ra "
            "MATCH (c:Camp {id:$camp_id}) "
            "MERGE (ra)-[:CAMP]->(c)",
            {"sido": sido, "sigungu": sigungu, "name": cat, "camp_id": rec.id},
        )

    # 4. 시설 → RegionAttribute → Camp (kind='Facility')
    for fac in rec.facilities:
        ...   # 동일 패턴
```

## FE 영향도

`fe/graph.html` 은 *스펙 열림* 모드라 신규 라벨/엣지를 자동 발견한다. 이 리팩토링 후 FE 변경은 *최소* — 새 노드/엣지 타입이 자동으로 칩에 등장하고 generic 렌더러가 그린다. 다만 의도 반영을 위해 NODE_REGISTRY/EDGE_REGISTRY 에 다음 항목 추가가 권장된다:

```js
NODE_REGISTRY.RegionAttribute = {
  shape: "tag",        // 또는 "round-tag"
  color: null,         // tagHue(label+name) 로 동적
  border: "#1a1a17",
  borderWidth: 0.7,
  textColor: "#1a1a17",
  size: 9,
  fontSize: 8,
  label: (p) => `${p.kind === "Category" ? "" : "🛠"} ${prettyTag(p.name)}`,
};

EDGE_REGISTRY.HAS_ATTRIBUTE = { color: "#6b4f2c", width: 1.4, style: "solid",  opacity: 0.78 };
EDGE_REGISTRY.CAMP          = { color: "#2c4a3e", width: 0.6, style: "solid",  opacity: 0.45 };
```

`region-tree` 레이아웃은 그대로 유효 — Region 이 root 면 BFS 가 자동으로 RegionAttribute 를 layer1, Camp 를 layer2 로 배치.

## 백엔드 API 영향

`/sites` `/facets` 등 기존 엔드포인트는 `LEGACY_*` 엣지가 살아 있으면 그대로 동작. 폐지 시 다음 cypher 로 변경:

```cypher
# /sites — 카테고리 + 시설 필터
MATCH (c:Camp)<-[:CAMP]-(:RegionAttribute)<-[:HAS_ATTRIBUTE]-(r:Region)
[<filter>]
RETURN c.id, c.name, c.lat, c.lon, r.sido, r.sigungu, ...
```

## 테스트 가이드

1. `tests/test_kg_builder.py` 에 `RegionAttribute` 노드/엣지 가 statement 로 생성되는지 검증.
2. `camfit-puller load-falkor` 후 `MATCH (r:Region)-[:HAS_ATTRIBUTE]->(ra)-[:CAMP]->(c) RETURN count(*)` 가 (camp 수) × (avg attributes per camp) ≈ 1000+ 정도 나오는지 sanity.
3. FE: graph.html 에서 force 레이아웃에 Region 이 hub, RegionAttribute 가 중간 클러스터, Camp 가 잎으로 자리잡는지 시각 확인.

## 마이그레이션 순서 (제안)

1. `kg_builder.py` 에 두 모델 동시 적재 (LEGACY 와 새 패턴 병행)
2. `/graph/*` 와 `/sites` 두 엔드포인트가 새 패턴을 우선 쿼리하도록 점진 변경
3. FE 시각 확인 + 사용자 피드백
4. LEGACY 엣지 제거, `Category/Facility` 노드 폐기
5. 통합 테스트 + 회귀

---

본 문서가 작성된 시점의 FE 그래프 뷰 코드는 `fe/graph.html`, 백엔드는 `camfit-puller/src/camfit_puller/api.py` 의 `/graph/*` 엔드포인트군. 두 곳 모두 *현재 모델* 에서 *새 모델* 로의 전환을 매끄럽게 받아들이도록 설계되어 있음 (스키마 자동 발견 + generic fallback).
