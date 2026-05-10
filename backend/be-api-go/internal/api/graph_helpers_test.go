// Unit tests for graph.go helper parity with Python.
package api

import (
	"reflect"
	"testing"
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
