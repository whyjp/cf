// FEATURED_AXES — boolean shortcut filters surfaced as 대표축 chips.
// 1:1 port of `domain.featured_axes.FEATURED_AXES`.
//
// Each axis is keyword-matched (case-insensitive substring) against the union
// of camp.collections + types + facilities + location_types + hashtags +
// description + brief. Adding a new axis is a one-entry append below; the
// backend re-derives `r.has_<id>` per request.
package domain

// FeaturedAxis mirrors the Python TypedDict.
type FeaturedAxis struct {
	ID       string   `json:"id"`       // snake_case, becomes r.has_<id>
	Ko       string   `json:"ko"`       // display label (Korean)
	Icon     string   `json:"icon"`     // emoji
	Tone     string   `json:"tone"`     // "" | "warm" | "bark"
	Keywords []string `json:"keywords"` // case-insensitive substring matches (mixed en/ko)
}

// FeaturedAxes is the canonical registry — order matches Python source.
//
// Trampoline keyword variants come from
// `pipeline discover-synonyms trampoline` in the Python codebase: typos
// (트램벌린) and the kid-toy synonym 퐁퐁 surfaced from the corpus itself.
// 방방 is the Korean colloquial standard (방방이 via substring).
var FeaturedAxes = []FeaturedAxis{
	{
		ID:       "valley",
		Ko:       "계곡",
		Icon:     "🌊",
		Tone:     "",
		Keywords: []string{"valley", "계곡"},
	},
	{
		ID:       "kids",
		Ko:       "키즈캠핑",
		Icon:     "🧒",
		Tone:     "warm",
		Keywords: []string{"kids", "키즈", "아이"},
	},
	{
		ID:   "trampoline",
		Ko:   "트램펄린",
		Icon: "🤸",
		Tone: "bark",
		Keywords: []string{
			"trampoline", "trampolin",
			"트램펄린", "트램폴린", "트렘펄린", "트렘폴린", "트램벌린",
			"방방", "퐁퐁",
		},
	},
	{
		ID:       "halloween",
		Ko:       "할로윈",
		Icon:     "🎃",
		Tone:     "warm",
		Keywords: []string{"할로윈", "핼러윈", "핼로윈", "halloween"},
	},
	{
		ID:       "cherry",
		Ko:       "벚꽃",
		Icon:     "🌸",
		Tone:     "warm",
		Keywords: []string{"벚꽃", "벚나무"},
	},
	{
		ID:       "autumn",
		Ko:       "단풍",
		Icon:     "🍁",
		Tone:     "bark",
		Keywords: []string{"단풍"},
	},
}

func init() {
	// Module-level invariants — fail-fast at import (mirrors Python module asserts).
	seen := make(map[string]bool, len(FeaturedAxes))
	for _, a := range FeaturedAxes {
		if seen[a.ID] {
			panic("FeaturedAxes has duplicate id: " + a.ID)
		}
		seen[a.ID] = true
		if len(a.Keywords) == 0 {
			panic("FeaturedAxes['" + a.ID + "'] has empty keywords")
		}
		switch a.Tone {
		case "", "warm", "bark":
		default:
			panic("FeaturedAxes['" + a.ID + "'] has invalid tone " + a.Tone)
		}
	}
}
