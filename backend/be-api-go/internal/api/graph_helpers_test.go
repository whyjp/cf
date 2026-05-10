// Unit tests for graph.go helper parity with Python.
package api

import (
	"context"
	"reflect"
	"testing"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

func TestPickNaturalKey(t *testing.T) {
	// id wins over everything.
	got := pickNaturalKey(map[string]any{"id": "abc", "name": "X", "title": "T"})
	if got != "abc" {
		t.Errorf("expected abc, got %q", got)
	}
	// name wins when id missing.
	got = pickNaturalKey(map[string]any{"name": "X"})
	if got != "X" {
		t.Errorf("expected X, got %q", got)
	}
	// fallback: first non-empty scalar `k=v` (sorted).
	got = pickNaturalKey(map[string]any{"zoo": "z", "alpha": "a"})
	if got != "alpha=a" {
		t.Errorf("expected alpha=a, got %q", got)
	}
	// empty map → empty string.
	if got = pickNaturalKey(map[string]any{}); got != "" {
		t.Errorf("expected empty, got %q", got)
	}
}

func TestNodeID(t *testing.T) {
	cases := []struct {
		label string
		props map[string]any
		want  string
	}{
		{"Camp", map[string]any{"id": "abc"}, "Camp:abc"},
		{"Region", map[string]any{"sido": "강원", "sigungu": "평창군"}, "Region:강원|평창군"},
		{"Region", map[string]any{"sido": "강원"}, "Region:강원"}, // sigungu empty → joined w/o trailing |
		{"Category", map[string]any{"name": "글램핑"}, "Category:글램핑"},
		{"Unknown", map[string]any{"name": "X"}, "Unknown:X"},
		{"Camp", map[string]any{}, "Camp:?"},
	}
	for _, c := range cases {
		got := nodeID(c.label, c.props)
		if got != c.want {
			t.Errorf("nodeID(%s, %v) = %q, want %q", c.label, c.props, got, c.want)
		}
	}
}

func TestParseLabels(t *testing.T) {
	cases := []struct {
		in   string
		want []string
	}{
		{"", nil},
		{"Camp", []string{"Camp"}},
		{"Camp,Region", []string{"Camp", "Region"}},
		{" Camp , Region ", []string{"Camp", "Region"}},
		{",,", []string{}}, // all empty after trim → empty slice (Python parity: list comprehension yields [])
	}
	for _, c := range cases {
		got := parseLabels(c.in)
		if c.want == nil {
			if got != nil {
				t.Errorf("parseLabels(%q) = %v, want nil", c.in, got)
			}
			continue
		}
		if !reflect.DeepEqual(got, c.want) {
			t.Errorf("parseLabels(%q) = %v, want %v", c.in, got, c.want)
		}
	}
}

func TestParseNodeID(t *testing.T) {
	cases := []struct {
		in              string
		wantL, wantNat  string
	}{
		{"Camp:abc", "Camp", "abc"},
		{"Region:강원|평창군", "Region", "강원|평창군"},
		{"plainid", "", "plainid"},
	}
	for _, c := range cases {
		l, n := parseNodeID(c.in)
		if l != c.wantL || n != c.wantNat {
			t.Errorf("parseNodeID(%q) = (%q,%q), want (%q,%q)",
				c.in, l, n, c.wantL, c.wantNat)
		}
	}
}

func TestWhereForNaturalKey(t *testing.T) {
	// Single-key label.
	w, p := whereForNaturalKey("Camp", "abc", "n")
	if w != "n.`id` = $k_id" {
		t.Errorf("Camp where: %q", w)
	}
	if p["k_id"] != "abc" {
		t.Errorf("Camp params: %v", p)
	}
	// Composite-key label.
	w, p = whereForNaturalKey("Region", "강원|평창군", "n")
	if w != "n.`sido` = $k_sido AND n.`sigungu` = $k_sigungu" {
		t.Errorf("Region where: %q", w)
	}
	if p["k_sido"] != "강원" || p["k_sigungu"] != "평창군" {
		t.Errorf("Region params: %v", p)
	}
	// Unknown label → id-or-name fallback.
	w, p = whereForNaturalKey("Unknown", "x", "n")
	if w != "(n.id = $k_id OR n.name = $k_id)" {
		t.Errorf("Unknown where: %q", w)
	}
	if p["k_id"] != "x" {
		t.Errorf("Unknown params: %v", p)
	}
}

func TestPrimaryTextKey(t *testing.T) {
	cases := []struct {
		label string
		want  string
	}{
		{"Camp", "id"},          // single key
		{"Region", "sigungu"},   // composite — last is most descriptive
		{"Category", "name"},
		{"Unknown", "name"},     // fallback
	}
	for _, c := range cases {
		if got := primaryTextKey(c.label); got != c.want {
			t.Errorf("primaryTextKey(%s) = %q, want %q", c.label, got, c.want)
		}
	}
}

// ─────────────────── D-7: ETA pruning helper tests (parity) ────────────────

func TestParseEtaMaxMinutes(t *testing.T) {
	cases := []struct {
		in   string
		want int
		ok   bool
	}{
		{"", 0, false},
		{"abc", 0, false},
		{"0", 0, false},
		{"1", 1, true},
		{"180", 180, true},
		{"1440", 1440, true},
		{"1441", 0, false},
		{"-5", 0, false},
	}
	for _, c := range cases {
		got, ok := parseEtaMaxMinutes(c.in)
		if got != c.want || ok != c.ok {
			t.Errorf("parseEtaMaxMinutes(%q) = (%d,%v), want (%d,%v)", c.in, got, ok, c.want, c.ok)
		}
	}
}

func TestCampDropped(t *testing.T) {
	keep := map[string]struct{}{"c1": {}, "c2": {}}
	// nil keep set → never drop
	if campDropped(nil, "Camp", map[string]any{"id": "x"}) {
		t.Error("nil keep set should never drop")
	}
	// non-Camp label → never drop (Concept etc.)
	if campDropped(keep, "Concept", map[string]any{"name": "valley"}) {
		t.Error("non-Camp must not be dropped")
	}
	// Camp ∈ keep → keep
	if campDropped(keep, "Camp", map[string]any{"id": "c1"}) {
		t.Error("c1 ∈ keep should not drop")
	}
	// Camp ∉ keep → drop
	if !campDropped(keep, "Camp", map[string]any{"id": "c9"}) {
		t.Error("c9 ∉ keep should drop")
	}
	// Camp without id → drop (Python `cid is not None else True`)
	if !campDropped(keep, "Camp", map[string]any{}) {
		t.Error("Camp w/o id should drop")
	}
	// Camp with empty-string id → drop
	if !campDropped(keep, "Camp", map[string]any{"id": ""}) {
		t.Error("Camp w/ empty id should drop")
	}
}

func TestCampPlaceFromProps(t *testing.T) {
	cases := []struct {
		name  string
		props map[string]any
		want  string
	}{
		{"sido + sigungu", map[string]any{"sido": "강원", "sigungu": "평창군"}, "강원 평창군"},
		{"only sido", map[string]any{"sido": "강원"}, "강원"},
		{"미지정 → fall to address", map[string]any{"sido": "(미지정)", "sigungu": "x", "address": "서울 성동구"}, "서울 성동구"},
		{"미지정 → fall to name", map[string]any{"sido": "(미지정)", "name": "홍길동캠핑장"}, "홍길동캠핑장"},
		{"empty everything → \"\"", map[string]any{}, ""},
		{"bytes from falkor", map[string]any{"sido": []byte("강원"), "sigungu": []byte("평창군")}, "강원 평창군"},
	}
	for _, c := range cases {
		got := campPlaceFromProps(c.props)
		if got != c.want {
			t.Errorf("%s: got %q, want %q", c.name, got, c.want)
		}
	}
}

func TestPropsHasLatLon(t *testing.T) {
	if propsHasLatLon(map[string]any{}) {
		t.Error("empty props must not have lat/lon")
	}
	if propsHasLatLon(map[string]any{"lat": 37.5}) {
		t.Error("lat only must not pass")
	}
	if !propsHasLatLon(map[string]any{"lat": 37.5, "lon": 127.0}) {
		t.Error("lat+lon must pass")
	}
	if propsHasLatLon(map[string]any{"lat": nil, "lon": 127.0}) {
		t.Error("nil lat must not pass")
	}
}

// fakeEtaProvider — minimal ports.EtaProvider for computeEtaKeep tests.
type fakeEtaProvider struct {
	minutesByPlace map[string]int
	err            error
}

func (f *fakeEtaProvider) DriveEta(ctx context.Context, origin, dest string, timeoutS float64) (*domain.EtaResult, error) {
	if f.err != nil {
		return nil, f.err
	}
	m, ok := f.minutesByPlace[dest]
	if !ok {
		return &domain.EtaResult{}, nil // no minutes
	}
	return &domain.EtaResult{Minutes: &m}, nil
}

func (f *fakeEtaProvider) DriveEtaBatch(ctx context.Context, origin string, dests []ports.EtaDest, concurrency int, timeoutS float64) (map[string]*domain.EtaResult, error) {
	if f.err != nil {
		return nil, f.err
	}
	out := map[string]*domain.EtaResult{}
	for _, d := range dests {
		if m, ok := f.minutesByPlace[d.Place]; ok {
			mc := m
			out[d.ID] = &domain.EtaResult{Minutes: &mc}
		} else {
			out[d.ID] = &domain.EtaResult{} // no minutes → drop
		}
	}
	return out, nil
}

func TestComputeEtaKeep_FiltersByMinutes(t *testing.T) {
	rows := []map[string]any{
		{"l_n": "Camp", "p_n": map[string]any{"id": "c1", "sido": "강원", "sigungu": "평창군", "lat": 37.5, "lon": 128.0}},
		{"l_n": "Camp", "p_n": map[string]any{"id": "c2", "sido": "제주", "sigungu": "서귀포시", "lat": 33.2, "lon": 126.5}},
		{"l_n": "Camp", "p_n": map[string]any{"id": "c3", "sido": "경기", "sigungu": "가평군", "lat": 37.8, "lon": 127.5}},
		// no lat/lon → must NOT be queried, NOT in keep, drops on prune
		{"l_n": "Camp", "p_n": map[string]any{"id": "c4", "sido": "강원", "sigungu": "철원군"}},
	}
	h := &GraphHandler{
		eta: &fakeEtaProvider{
			minutesByPlace: map[string]int{
				"강원 평창군":   90,
				"제주 서귀포시":  500, // over budget
				"경기 가평군":   60,
			},
		},
	}
	keep, warn := h.computeEtaKeep(context.Background(), rows, "강남역", 120)
	if warn != "" {
		t.Errorf("unexpected warning: %s", warn)
	}
	if _, ok := keep["c1"]; !ok {
		t.Error("c1 (90 min ≤ 120) should be kept")
	}
	if _, ok := keep["c2"]; ok {
		t.Error("c2 (500 min > 120) should be dropped")
	}
	if _, ok := keep["c3"]; !ok {
		t.Error("c3 (60 min ≤ 120) should be kept")
	}
	if _, ok := keep["c4"]; ok {
		t.Error("c4 (no coords) should not appear in keep set")
	}
}

func TestComputeEtaKeep_NoCampsInRows(t *testing.T) {
	rows := []map[string]any{
		{"l_n": "Concept", "p_n": map[string]any{"name": "valley"}},
	}
	h := &GraphHandler{eta: &fakeEtaProvider{}}
	keep, warn := h.computeEtaKeep(context.Background(), rows, "강남역", 120)
	if warn != "" {
		t.Errorf("unexpected warning: %s", warn)
	}
	if len(keep) != 0 {
		t.Errorf("expected empty keep, got %v", keep)
	}
}

func TestEdgeElement(t *testing.T) {
	src := map[string]any{"id": "c1"}
	dst := map[string]any{"sido": "강원", "sigungu": "평창군"}
	got := edgeElement("LOCATED_IN", src, dst, "Camp", "Region", 7)
	data := got["data"].(map[string]any)
	if data["id"] != "e:7:LOCATED_IN" {
		t.Errorf("edge id: %v", data["id"])
	}
	if data["source"] != "Camp:c1" {
		t.Errorf("edge source: %v", data["source"])
	}
	if data["target"] != "Region:강원|평창군" {
		t.Errorf("edge target: %v", data["target"])
	}
	if data["label"] != "LOCATED_IN" {
		t.Errorf("edge label: %v", data["label"])
	}
}
