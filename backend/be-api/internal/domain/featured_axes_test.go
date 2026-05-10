package domain

import "testing"

func TestFeaturedAxesInvariants(t *testing.T) {
	if len(FeaturedAxes) == 0 {
		t.Fatal("FeaturedAxes empty")
	}
	seen := map[string]bool{}
	for _, a := range FeaturedAxes {
		if seen[a.ID] {
			t.Fatalf("duplicate id: %s", a.ID)
		}
		seen[a.ID] = true
		if len(a.Keywords) == 0 {
			t.Fatalf("axis %s has no keywords", a.ID)
		}
	}
	// Spot-check the canonical axes.
	wantIDs := []string{"valley", "kids", "trampoline", "halloween", "cherry", "autumn"}
	for _, id := range wantIDs {
		if !seen[id] {
			t.Fatalf("expected axis %s missing", id)
		}
	}
}
