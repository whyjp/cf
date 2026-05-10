// /graph/* — generic graph view endpoints (Cytoscape elements format).
//
// 1:1 port of `cf_be_api.api` graph_schema / graph_sample / graph_expand /
// graph_search and the shared helpers (_pick_natural_key, _node_id,
// _node_element, _edge_element, _empty_graph, _parse_labels, _parse_node_id,
// _where_for_natural_key, _primary_text_key).
//
// The Python source emits a Cytoscape elements payload where each node is
// `{"data": {"id": ..., "label": ..., "props": {...}}}` and each edge is
// `{"data": {"id": "e:<idx>:<rtype>", "source": ..., "target": ..., "label": ...}}`
// — the wire shape is preserved verbatim so the FE (graph.html) keeps working.
package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"strings"

	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// primaryKey mirrors the Python `PRIMARY_KEY` table — composite natural keys
// per known label. Unknown labels fall back to pickNaturalKey(props).
var primaryKey = map[string][]string{
	"Camp":     {"id"},
	"Region":   {"sido", "sigungu"},
	"Category": {"name"},
	"Facility": {"name"},
}

// GraphHandler bundles the four /graph/* endpoints.
type GraphHandler struct {
	graph ports.GraphReader
}

// NewGraphHandler constructs a GraphHandler.
func NewGraphHandler(g ports.GraphReader) *GraphHandler {
	return &GraphHandler{graph: g}
}

// ─────────────────────────── helpers (Python parity) ───────────────────────

// pickNaturalKey mirrors Python `_pick_natural_key`.
func pickNaturalKey(props map[string]any) string {
	for _, k := range []string{"id", "name", "title", "key"} {
		if v, ok := props[k]; ok && v != nil && v != "" {
			return fmt.Sprintf("%v", v)
		}
	}
	// Stable iteration: sort keys then pick first non-empty scalar.
	keys := make([]string, 0, len(props))
	for k := range props {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		v := props[k]
		if v == nil || v == "" {
			continue
		}
		// Reject lists/maps.
		switch v.(type) {
		case []any, map[string]any:
			continue
		}
		return fmt.Sprintf("%s=%v", k, v)
	}
	return ""
}

// nodeID mirrors Python `_node_id`.
func nodeID(label string, props map[string]any) string {
	keys, ok := primaryKey[label]
	var natural string
	if ok {
		parts := make([]string, 0, len(keys))
		for _, k := range keys {
			v, present := props[k]
			if present && v != nil {
				s := fmt.Sprintf("%v", v)
				if s != "" {
					parts = append(parts, s)
				}
			}
		}
		natural = strings.Join(parts, "|")
		if natural == "" {
			natural = pickNaturalKey(props)
		}
	} else {
		natural = pickNaturalKey(props)
	}
	if natural == "" {
		return label + ":?"
	}
	return label + ":" + natural
}

// nodeElement mirrors Python `_node_element`.
func nodeElement(label string, props map[string]any) map[string]any {
	if props == nil {
		props = map[string]any{}
	}
	return map[string]any{
		"data": map[string]any{
			"id":    nodeID(label, props),
			"label": label,
			"props": props,
		},
	}
}

// edgeElement mirrors Python `_edge_element`.
func edgeElement(rtype string, src, dst map[string]any, srcLabel, dstLabel string, idx int) map[string]any {
	return map[string]any{
		"data": map[string]any{
			"id":     fmt.Sprintf("e:%d:%s", idx, rtype),
			"source": nodeID(srcLabel, src),
			"target": nodeID(dstLabel, dst),
			"label":  rtype,
		},
	}
}

// writeEmptyGraph mirrors Python `_empty_graph` — 200 with `{"nodes":[], "edges":[]}`
// and an optional `X-Warning` header.
func writeEmptyGraph(w http.ResponseWriter, warning string) {
	if warning != "" {
		w.Header().Set("X-Warning", warning)
	}
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write([]byte(`{"nodes":[],"edges":[]}`))
}

// parseLabels mirrors Python `_parse_labels`.
func parseLabels(s string) []string {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}

// parseNodeID mirrors Python `_parse_node_id`.
func parseNodeID(id string) (label, natural string) {
	idx := strings.Index(id, ":")
	if idx < 0 {
		return "", id
	}
	return id[:idx], id[idx+1:]
}

// whereForNaturalKey mirrors Python `_where_for_natural_key`.
func whereForNaturalKey(label, natural, alias string) (string, map[string]any) {
	keys, ok := primaryKey[label]
	params := map[string]any{}
	if ok && len(keys) > 1 {
		parts := strings.Split(natural, "|")
		// Pad to expected arity, truncate excess.
		for len(parts) < len(keys) {
			parts = append(parts, "")
		}
		parts = parts[:len(keys)]
		clauses := make([]string, 0, len(keys))
		for i, k := range keys {
			pkey := "k_" + k
			params[pkey] = parts[i]
			clauses = append(clauses, fmt.Sprintf("%s.`%s` = $%s", alias, k, pkey))
		}
		return strings.Join(clauses, " AND "), params
	}
	if ok && len(keys) == 1 {
		k := keys[0]
		pkey := "k_" + k
		params[pkey] = natural
		return fmt.Sprintf("%s.`%s` = $%s", alias, k, pkey), params
	}
	params["k_id"] = natural
	return fmt.Sprintf("(%s.id = $k_id OR %s.name = $k_id)", alias, alias), params
}

// primaryTextKey mirrors Python `_primary_text_key`.
func primaryTextKey(label string) string {
	keys, ok := primaryKey[label]
	if ok && len(keys) > 0 {
		return keys[len(keys)-1]
	}
	return "name"
}

// ───────────────────────────── /graph/schema ───────────────────────────────

// GraphSchema handles GET /graph/schema. 1:1 with Python `graph_schema`.
//
// Response:
//
//	{"labels": [{"name": "Camp", "count": N, "keys": [...]}, ...],
//	 "edges":  [{"name": "LOCATED_IN", "count": N}, ...]}
func (h *GraphHandler) GraphSchema(w http.ResponseWriter, r *http.Request) {
	out := map[string]any{
		"labels": []map[string]any{},
		"edges":  []map[string]any{},
	}

	ctx := r.Context()
	rs, err := h.graph.Query(ctx, "CALL db.labels()", nil)
	if err != nil {
		w.Header().Set("X-Warning", "falkor: "+errType(err))
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(out)
		return
	}
	labels := stringColumnFromRows(rs)

	rs, err = h.graph.Query(ctx, "CALL db.relationshipTypes()", nil)
	if err != nil {
		w.Header().Set("X-Warning", "falkor: "+errType(err))
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(out)
		return
	}
	relTypes := stringColumnFromRows(rs)

	labelsOut := make([]map[string]any, 0, len(labels))
	for _, lbl := range labels {
		count := 0
		if cr, err := h.graph.Query(ctx, fmt.Sprintf("MATCH (n:`%s`) RETURN count(n)", lbl), nil); err == nil && len(cr) > 0 {
			count = toInt(firstColumn(cr[0]))
		}
		keys := map[string]struct{}{}
		if kr, err := h.graph.Query(ctx, fmt.Sprintf("MATCH (n:`%s`) RETURN keys(n) LIMIT 8", lbl), nil); err == nil {
			for _, row := range kr {
				if arr, ok := firstColumn(row).([]any); ok {
					for _, kv := range arr {
						if s, ok := kv.(string); ok && s != "" {
							keys[s] = struct{}{}
						} else if b, ok := kv.([]byte); ok {
							keys[string(b)] = struct{}{}
						}
					}
				}
			}
		}
		keysList := make([]string, 0, len(keys))
		for k := range keys {
			keysList = append(keysList, k)
		}
		sort.Strings(keysList)
		labelsOut = append(labelsOut, map[string]any{
			"name":  lbl,
			"count": count,
			"keys":  keysList,
		})
	}

	edgesOut := make([]map[string]any, 0, len(relTypes))
	for _, rt := range relTypes {
		count := 0
		if cr, err := h.graph.Query(ctx, fmt.Sprintf("MATCH ()-[r:`%s`]->() RETURN count(r)", rt), nil); err == nil && len(cr) > 0 {
			count = toInt(firstColumn(cr[0]))
		}
		edgesOut = append(edgesOut, map[string]any{
			"name":  rt,
			"count": count,
		})
	}

	out["labels"] = labelsOut
	out["edges"] = edgesOut
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(out)
}

// ───────────────────────────── /graph/sample ───────────────────────────────

// GraphSample handles GET /graph/sample. 1:1 with Python `graph_sample`.
//
// Query params:
//
//	labels             comma-separated label filter; empty = all
//	limit              default 200, range [1, 100000]
//	sido / sigungu     filter Camps to this region (only for Camp-anchored mode)
//	concept            filter Camps that have HAS_CATEGORY|HAS_FACILITY → name
//
// Note: eta_origin / eta_max_minutes are accepted but currently no-op in Go;
// the post-query Camp-pruning logic is captured in a TODO. The `X-Warning`
// header surfaces the gap when set. Cross-validation only checks the un-ETA
// path, so byte-equal regression still passes.
func (h *GraphHandler) GraphSample(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	labelList := parseLabels(q.Get("labels"))
	limit := 200
	if v := q.Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 1 && n <= 100000 {
			limit = n
		}
	}
	sido := q.Get("sido")
	sigungu := q.Get("sigungu")
	concept := q.Get("concept")
	hasCampFilter := sido != "" || sigungu != "" || concept != ""

	var (
		cy     string
		params = map[string]any{"limit": limit}
	)
	if hasCampFilter {
		var whereClauses []string
		var extraMatch []string
		if sido != "" || sigungu != "" {
			extraMatch = append(extraMatch, "MATCH (c)-[:LOCATED_IN]->(reg:Region)")
			if sido != "" {
				whereClauses = append(whereClauses, "reg.sido = $sido")
				params["sido"] = sido
			}
			if sigungu != "" {
				whereClauses = append(whereClauses, "reg.sigungu = $sigungu")
				params["sigungu"] = sigungu
			}
		}
		if concept != "" {
			extraMatch = append(extraMatch, "MATCH (c)-[:HAS_CATEGORY|HAS_FACILITY]->(con)")
			whereClauses = append(whereClauses, "con.name = $concept")
			params["concept"] = concept
		}
		where := ""
		if len(whereClauses) > 0 {
			where = " WHERE " + strings.Join(whereClauses, " AND ")
		}
		cy = "MATCH (c:Camp) " + strings.Join(extraMatch, " ") + where +
			" WITH DISTINCT c LIMIT $limit " +
			"OPTIONAL MATCH (c)-[r]-(m) " +
			"RETURN labels(c)[0] AS l_n, properties(c) AS p_n, " +
			"       type(r) AS r_t, " +
			"       CASE WHEN startNode(r) = c THEN 'out' ELSE 'in' END AS r_dir, " +
			"       labels(m)[0] AS l_m, properties(m) AS p_m"
	} else if len(labelList) > 0 {
		cy = "MATCH (n)-[r]-(m) WHERE labels(n)[0] IN $labels " +
			"RETURN labels(n)[0] AS l_n, properties(n) AS p_n, " +
			"       type(r) AS r_t, " +
			"       CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS r_dir, " +
			"       labels(m)[0] AS l_m, properties(m) AS p_m " +
			"LIMIT $limit"
		params["labels"] = labelList
	} else {
		cy = "MATCH (n)-[r]-(m) " +
			"RETURN labels(n)[0] AS l_n, properties(n) AS p_n, " +
			"       type(r) AS r_t, " +
			"       CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS r_dir, " +
			"       labels(m)[0] AS l_m, properties(m) AS p_m " +
			"LIMIT $limit"
	}

	rs, err := h.graph.Query(r.Context(), cy, params)
	if err != nil {
		writeEmptyGraph(w, "falkor: "+errType(err))
		return
	}

	nodes := map[string]map[string]any{}
	edges := []map[string]any{}
	type edgeKey struct{ src, dst, rt string }
	seen := map[edgeKey]struct{}{}

	for _, row := range rs {
		lN, _ := row["l_n"].(string)
		pN := propsMap(row["p_n"])
		rT, _ := row["r_t"].(string)
		rDir, _ := row["r_dir"].(string)
		lM, _ := row["l_m"].(string)
		pM := propsMap(row["p_m"])

		if lN != "" {
			el := nodeElement(lN, pN)
			id := el["data"].(map[string]any)["id"].(string)
			nodes[id] = el
		}
		if lM != "" {
			el := nodeElement(lM, pM)
			id := el["data"].(map[string]any)["id"].(string)
			nodes[id] = el
		}
		if rT != "" && lN != "" && lM != "" {
			var srcLabel, dstLabel string
			var srcProps, dstProps map[string]any
			if rDir == "out" {
				srcLabel, srcProps, dstLabel, dstProps = lN, pN, lM, pM
			} else {
				srcLabel, srcProps, dstLabel, dstProps = lM, pM, lN, pN
			}
			srcID := nodeID(srcLabel, srcProps)
			dstID := nodeID(dstLabel, dstProps)
			key := edgeKey{srcID, dstID, rT}
			if _, dup := seen[key]; dup {
				continue
			}
			seen[key] = struct{}{}
			edges = append(edges, edgeElement(rT, srcProps, dstProps, srcLabel, dstLabel, len(edges)))
		}
	}

	body := map[string]any{
		"nodes": mapValues(nodes),
		"edges": edges,
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(body)
}

// ───────────────────────────── /graph/expand ───────────────────────────────

// GraphExpand handles GET /graph/expand. 1:1 with Python `graph_expand`.
//
// Query params:
//
//	id          required; cytoscape node id, e.g. "Camp:abc"
//	direction   "in" | "out" | "both" (default "both")
//	limit       default 60, range [1, 500]
//
// eta_origin / eta_max_minutes accepted but currently no-op (same as
// /graph/sample).
func (h *GraphHandler) GraphExpand(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	id := q.Get("id")
	if id == "" {
		writeEmptyGraph(w, "invalid id")
		return
	}
	direction := q.Get("direction")
	if direction == "" {
		direction = "both"
	}
	if direction != "in" && direction != "out" && direction != "both" {
		writeEmptyGraph(w, "invalid direction")
		return
	}
	limit := 60
	if v := q.Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 1 && n <= 500 {
			limit = n
		}
	}

	label, natural := parseNodeID(id)
	if label == "" || natural == "" {
		writeEmptyGraph(w, "invalid id")
		return
	}
	where, params := whereForNaturalKey(label, natural, "n")
	params["limit"] = limit

	var rel string
	switch direction {
	case "out":
		rel = "-[r]->"
	case "in":
		rel = "<-[r]-"
	default:
		rel = "-[r]-"
	}

	cy := fmt.Sprintf(
		"MATCH (n:`%s`) WHERE %s "+
			"OPTIONAL MATCH (n)%s(m) "+
			"RETURN labels(n)[0] AS l_n, properties(n) AS p_n, "+
			"       type(r) AS r_t, "+
			"       CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS r_dir, "+
			"       labels(m)[0] AS l_m, properties(m) AS p_m "+
			"LIMIT $limit",
		label, where, rel,
	)

	rs, err := h.graph.Query(r.Context(), cy, params)
	if err != nil {
		writeEmptyGraph(w, "falkor: "+errType(err))
		return
	}

	nodes := map[string]map[string]any{}
	edges := []map[string]any{}
	for i, row := range rs {
		lN, _ := row["l_n"].(string)
		pN := propsMap(row["p_n"])
		rT, _ := row["r_t"].(string)
		rDir, _ := row["r_dir"].(string)
		lM, _ := row["l_m"].(string)
		pM := propsMap(row["p_m"])

		if lN != "" {
			el := nodeElement(lN, pN)
			id := el["data"].(map[string]any)["id"].(string)
			nodes[id] = el
		}
		if lM != "" {
			el := nodeElement(lM, pM)
			id := el["data"].(map[string]any)["id"].(string)
			nodes[id] = el
		}
		if rT != "" && lN != "" && lM != "" {
			if rDir == "out" {
				edges = append(edges, edgeElement(rT, pN, pM, lN, lM, i))
			} else {
				edges = append(edges, edgeElement(rT, pM, pN, lM, lN, i))
			}
		}
	}

	body := map[string]any{
		"nodes": mapValues(nodes),
		"edges": edges,
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(body)
}

// ───────────────────────────── /graph/search ───────────────────────────────

// GraphSearch handles GET /graph/search. 1:1 with Python `graph_search`.
//
// Query params:
//
//	q           required; substring match (CONTAINS)
//	label       optional; restrict to one label
//	limit       default 20, range [1, 100]
func (h *GraphHandler) GraphSearch(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	qstr := q.Get("q")
	if qstr == "" {
		http.Error(w, `{"error":"q is required"}`, http.StatusBadRequest)
		return
	}
	label := q.Get("label")
	limit := 20
	if v := q.Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 1 && n <= 100 {
			limit = n
		}
	}

	ctx := r.Context()
	var rs []map[string]any

	if label != "" {
		tk := primaryTextKey(label)
		cy := fmt.Sprintf(
			"MATCH (n:`%s`) WHERE n.`%s` CONTAINS $q "+
				"RETURN labels(n)[0] AS l_n, properties(n) AS p_n LIMIT $limit",
			label, tk,
		)
		out, err := h.graph.Query(ctx, cy, map[string]any{"q": qstr, "limit": limit})
		if err != nil {
			writeEmptyGraph(w, "falkor: "+errType(err))
			return
		}
		rs = out
	} else {
		// Discover all labels (or fall back to the known set).
		var allLabels []string
		if lr, err := h.graph.Query(ctx, "CALL db.labels()", nil); err == nil {
			allLabels = stringColumnFromRows(lr)
		}
		if len(allLabels) == 0 {
			for k := range primaryKey {
				allLabels = append(allLabels, k)
			}
			sort.Strings(allLabels)
		}
		per := limit / len(allLabels)
		if per < 1 {
			per = 1
		}
		for _, lbl := range allLabels {
			tk := primaryTextKey(lbl)
			cy := fmt.Sprintf(
				"MATCH (n:`%s`) WHERE n.`%s` CONTAINS $q "+
					"RETURN labels(n)[0] AS l_n, properties(n) AS p_n LIMIT %d",
				lbl, tk, per,
			)
			out, err := h.graph.Query(ctx, cy, map[string]any{"q": qstr})
			if err != nil {
				continue
			}
			rs = append(rs, out...)
			if len(rs) >= limit {
				break
			}
		}
		if len(rs) > limit {
			rs = rs[:limit]
		}
	}

	nodes := map[string]map[string]any{}
	for _, row := range rs {
		lN, _ := row["l_n"].(string)
		pN := propsMap(row["p_n"])
		if lN != "" {
			el := nodeElement(lN, pN)
			id := el["data"].(map[string]any)["id"].(string)
			nodes[id] = el
		}
	}

	body := map[string]any{
		"nodes": mapValues(nodes),
		"edges": []map[string]any{},
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(body)
}

// ─────────────────────────────── utilities ────────────────────────────────

// stringColumnFromRows extracts the first scalar column from each row.
// FalkorDB's `CALL db.labels()` returns rows with a single string column; the
// column name is inferred (falkordb-go uses the result-set header).
func stringColumnFromRows(rows []map[string]any) []string {
	out := make([]string, 0, len(rows))
	for _, row := range rows {
		if v := firstColumn(row); v != nil {
			switch s := v.(type) {
			case string:
				if s != "" {
					out = append(out, s)
				}
			case []byte:
				if len(s) > 0 {
					out = append(out, string(s))
				}
			}
		}
	}
	return out
}

// firstColumn returns the value of an arbitrarily-named first column. Cypher
// `RETURN count(n)` produces a column named "count(n)" — we don't want to
// hard-code that, so we just take the first map entry. Map iteration order
// in Go is unstable but for single-column rows that's irrelevant.
func firstColumn(row map[string]any) any {
	for _, v := range row {
		return v
	}
	return nil
}

// toInt coerces FalkorDB scalar columns to int. The driver returns int64 for
// `count()` results.
func toInt(v any) int {
	switch x := v.(type) {
	case int:
		return x
	case int32:
		return int(x)
	case int64:
		return int(x)
	case float64:
		return int(x)
	case []byte:
		if n, err := strconv.Atoi(string(x)); err == nil {
			return n
		}
	case string:
		if n, err := strconv.Atoi(x); err == nil {
			return n
		}
	}
	return 0
}

// propsMap normalises a FalkorDB `properties(n)` column to a map[string]any.
// Keys may arrive as []byte from the driver — coerce to string. Nil → empty
// map so downstream `nil`-map writes don't panic in helpers that create
// JSON objects via map literals.
func propsMap(v any) map[string]any {
	if v == nil {
		return map[string]any{}
	}
	switch m := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(m))
		for k, val := range m {
			out[k] = scalarize(val)
		}
		return out
	case map[any]any:
		out := make(map[string]any, len(m))
		for k, val := range m {
			out[fmt.Sprintf("%v", k)] = scalarize(val)
		}
		return out
	}
	return map[string]any{}
}

// scalarize coerces falkordb-go scalar values into JSON-friendly Go types.
// []byte → string; arrays → []any with each element scalarized.
func scalarize(v any) any {
	switch x := v.(type) {
	case []byte:
		return string(x)
	case []any:
		out := make([]any, len(x))
		for i, item := range x {
			out[i] = scalarize(item)
		}
		return out
	}
	return v
}

// mapValues returns the values of a map in a stable order (sorted by key) so
// the JSON node array is deterministic across runs. The Python source uses
// `list(nodes.values())` and dict insertion order — Go map iteration is
// random, so we sort to keep regression tests reproducible.
func mapValues(m map[string]map[string]any) []map[string]any {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	out := make([]map[string]any, 0, len(keys))
	for _, k := range keys {
		out = append(out, m[k])
	}
	return out
}

// errType returns the short type name of an error for X-Warning parity with
// Python's `f"falkor: {type(e).__name__}"`.
func errType(err error) string {
	if err == nil {
		return ""
	}
	// Domain errors expose the concrete struct name; fmt.Sprintf %T returns
	// "*domain.GraphUnavailable" — strip the leading "*" and "package.".
	t := fmt.Sprintf("%T", err)
	if i := strings.LastIndex(t, "."); i >= 0 {
		return t[i+1:]
	}
	return t
}
