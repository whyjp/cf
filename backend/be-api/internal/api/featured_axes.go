// /featured-axes HTTP handler — D-4 read path.
//
// 1:1 with the Python `cf_be_api.api.featured_axes` handler. Returns the FE
// chip metadata derived from `domain.FeaturedAxes`. The `keywords` field is
// intentionally OMITTED — only id/ko/icon/tone are projected. (BFF projection
// owns the actual keyword matching after SP-A A3.)
package api

import (
	"encoding/json"
	"net/http"

	"github.com/whyjp/cf/be-api/internal/domain"
)

// FeaturedAxesChip is the projected shape — `id`, `ko`, `icon`, `tone`.
type FeaturedAxesChip struct {
	ID   string `json:"id"`
	Ko   string `json:"ko"`
	Icon string `json:"icon"`
	Tone string `json:"tone"`
}

// FeaturedAxes handles GET /featured-axes.
func FeaturedAxes(w http.ResponseWriter, r *http.Request) {
	out := make([]FeaturedAxesChip, 0, len(domain.FeaturedAxes))
	for _, a := range domain.FeaturedAxes {
		out = append(out, FeaturedAxesChip{
			ID: a.ID, Ko: a.Ko, Icon: a.Icon, Tone: a.Tone,
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(out)
}
