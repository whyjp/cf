// RebuildGraph use-case — 1:1 with Python `usecases.rebuild_graph.RebuildGraph`.
//
// Wipes the FalkorDB graph then re-creates Camp / Region / Category / Facility /
// Hashtag / LocationType / Collection / Concept / Theme nodes and the edges
// between them, sourced from PG truth. Idempotent: safe to re-run after any
// signal/concept/theme refresh.
//
// Node schema:
//
//	Camp(id, name, lat, lon, url, address, description)
//	Region(sido, sigungu)
//	Category(name)         — from Camp.types
//	Facility(name)         — from Camp.facilities + additional_facilities
//	Hashtag(name)
//	LocationType(name)
//	Collection(name)       — camfit native curation
//	Concept(id, name, source) — auto-derived
//	Theme(id, label, count)   — emergent clusters
//
// Edges:
//
//	(Camp)-[:LOCATED_IN]->(Region)
//	(Camp)-[:HAS_CATEGORY]->(Category)
//	(Camp)-[:HAS_FACILITY]->(Facility)
//	(Camp)-[:HAS_HASHTAG]->(Hashtag)
//	(Camp)-[:HAS_LOCATION]->(LocationType)
//	(Camp)-[:IN_COLLECTION]->(Collection)
//	(Camp)-[:HAS_CONCEPT {score}]->(Concept)   — only when score > 0
//	(Camp)-[:IN_THEME]->(Theme)
package usecases

import (
	"context"

	"github.com/whyjp/cf/be-api/internal/ports"
)

// RebuildGraph executes the rebuild against a GraphReader (which doubles as
// writer because the underlying FalkorGraph executes arbitrary Cypher).
type RebuildGraph struct {
	camps    ports.CampReader
	concepts ports.ConceptReader
	themes   ports.ThemeReader
	graph    ports.GraphReader
}

// NewRebuildGraph constructs a RebuildGraph use-case. concepts/themes use the
// read-side ports — `for_camp` exists on both, which is all this use-case
// needs in addition to `all()`.
func NewRebuildGraph(
	camps ports.CampReader,
	concepts ports.ConceptReader,
	themes ports.ThemeReader,
	graph ports.GraphReader,
) *RebuildGraph {
	return &RebuildGraph{camps: camps, concepts: concepts, themes: themes, graph: graph}
}

// Execute wipes + repopulates the graph. Returns a count map identical in
// shape to the Python `RebuildGraph.execute()` return:
//
//	{"camps": N, "concepts": M, "themes": K,
//	 "concept_edges": E1, "theme_edges": E2}
func (uc *RebuildGraph) Execute(ctx context.Context) (map[string]int, error) {
	// 1. Wipe the existing graph.
	if err := uc.graph.Reset(ctx, ""); err != nil {
		return nil, err
	}

	// 2. Iterate every Camp — reuse ListCamps with no filters and the P5 cap.
	camps, err := uc.camps.ListCamps(ctx, ports.ListCampsOptions{Limit: 100000})
	if err != nil {
		return nil, err
	}

	const campCypher = `
MERGE (c:Camp {id:$id})
SET c.name=$name, c.lat=$lat, c.lon=$lon, c.url=$url,
    c.address=$addr, c.description=$desc
MERGE (r:Region {sido:$sido, sigungu:$sigungu})
MERGE (c)-[:LOCATED_IN]->(r)
FOREACH (t IN $types | MERGE (cat:Category {name:t}) MERGE (c)-[:HAS_CATEGORY]->(cat))
FOREACH (f IN $facs   | MERGE (ff:Facility {name:f}) MERGE (c)-[:HAS_FACILITY]->(ff))
FOREACH (h IN $hashtags | MERGE (ht:Hashtag {name:h}) MERGE (c)-[:HAS_HASHTAG]->(ht))
FOREACH (l IN $locs   | MERGE (lt:LocationType {name:l}) MERGE (c)-[:HAS_LOCATION]->(lt))
FOREACH (k IN $cols   | MERGE (col:Collection {name:k}) MERGE (c)-[:IN_COLLECTION]->(col))
`

	for _, camp := range camps {
		var lat, lon any
		if camp.Geo != nil {
			lat, lon = camp.Geo.Lat, camp.Geo.Lon
		}
		params := map[string]any{
			"id":       camp.ID,
			"name":     camp.Name,
			"lat":      lat,
			"lon":      lon,
			"url":      ptrStr(camp.URL),
			"addr":     ptrStr(camp.Address),
			"desc":     ptrStr(camp.Description),
			"sido":     camp.Region.Sido,
			"sigungu":  camp.Region.Sigungu,
			"types":    camp.Types,
			"facs":     uniqueStrings(camp.Facilities, camp.AdditionalFacilities),
			"hashtags": camp.Hashtags,
			"locs":     camp.LocationTypes,
			"cols":     camp.Collections,
		}
		if _, err := uc.graph.Query(ctx, campCypher, params); err != nil {
			return nil, err
		}
	}

	// 3. Concept and Theme nodes.
	concepts, err := uc.concepts.All(ctx)
	if err != nil {
		return nil, err
	}
	for _, c := range concepts {
		if _, err := uc.graph.Query(ctx,
			"MERGE (k:Concept {id:$id}) SET k.name=$name, k.source=$src",
			map[string]any{"id": c.ID, "name": c.Name, "src": c.Source},
		); err != nil {
			return nil, err
		}
	}

	themes, err := uc.themes.All(ctx)
	if err != nil {
		return nil, err
	}
	for _, t := range themes {
		if _, err := uc.graph.Query(ctx,
			"MERGE (t:Theme {id:$id}) SET t.label=$label, t.count=$n",
			map[string]any{"id": t.ID, "label": t.Label, "n": t.MemberCount},
		); err != nil {
			return nil, err
		}
	}

	// 4. Camp ↔ Concept (only positive aggregated scores) and Camp ↔ Theme.
	conceptEdges := 0
	themeEdges := 0
	for _, camp := range camps {
		ccs, err := uc.concepts.ForCamp(ctx, camp.ID)
		if err != nil {
			return nil, err
		}
		for _, cc := range ccs {
			if cc.Score > 0 {
				if _, err := uc.graph.Query(ctx,
					`MATCH (c:Camp {id:$cid}), (k:Concept {id:$kid})
					 MERGE (c)-[r:HAS_CONCEPT]->(k) SET r.score=$s`,
					map[string]any{"cid": cc.CampID, "kid": cc.ConceptID, "s": cc.Score},
				); err != nil {
					return nil, err
				}
				conceptEdges++
			}
		}
		t, err := uc.themes.ForCamp(ctx, camp.ID)
		if err != nil {
			return nil, err
		}
		if t != nil {
			if _, err := uc.graph.Query(ctx,
				`MATCH (c:Camp {id:$cid}), (t:Theme {id:$tid})
				 MERGE (c)-[:IN_THEME]->(t)`,
				map[string]any{"cid": camp.ID, "tid": t.ID},
			); err != nil {
				return nil, err
			}
			themeEdges++
		}
	}

	return map[string]int{
		"camps":         len(camps),
		"concepts":      len(concepts),
		"themes":        len(themes),
		"concept_edges": conceptEdges,
		"theme_edges":   themeEdges,
	}, nil
}

func ptrStr(p *string) any {
	if p == nil {
		return nil
	}
	return *p
}

// uniqueStrings returns the union of multiple string slices in stable order
// (first occurrence wins). Mirrors `list(set(camp.facilities + camp.additional_facilities))`.
func uniqueStrings(slices ...[]string) []string {
	seen := map[string]struct{}{}
	out := []string{}
	for _, s := range slices {
		for _, v := range s {
			if _, ok := seen[v]; ok {
				continue
			}
			seen[v] = struct{}{}
			out = append(out, v)
		}
	}
	return out
}
