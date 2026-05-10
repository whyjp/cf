// /sites HTTP handler — D-2 read path.
//
// Query parameters mirror the Python `api.sites` FastAPI handler exactly:
//
//	region=…              → opts.Sido (note: Python aliases region→sido)
//	sigungu=…             → opts.Sigungu
//	concept=… (repeated)  → opts.Concept (AND)
//	concepts_any=a,b      → opts.ConceptsAny (OR; comma-split)
//	min_score=…           → opts.MinScore
//	max_score=…           → opts.MaxScore
//	bbox=lon1,lat1,lon2,lat2 → opts.Bbox (silently dropped on parse error)
//	limit=N               → opts.Limit (default 10000)
package api

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/whyjp/cf/be-api/internal/ports"
	"github.com/whyjp/cf/be-api/internal/usecases"
)

// SitesHandler wires the /sites endpoint to its use-case.
type SitesHandler struct {
	listCamps *usecases.ListCamps
}

// NewSitesHandler constructs a SitesHandler.
func NewSitesHandler(uc *usecases.ListCamps) *SitesHandler {
	return &SitesHandler{listCamps: uc}
}

// ServeHTTP handles GET /sites.
func (h *SitesHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	opts := ports.ListCampsOptions{Limit: 10000}

	if v := q.Get("region"); v != "" {
		s := v
		opts.Sido = &s
	}
	if v := q.Get("sigungu"); v != "" {
		s := v
		opts.Sigungu = &s
	}
	if vs := q["concept"]; len(vs) > 0 {
		opts.Concept = append(opts.Concept, vs...)
	}
	if v := q.Get("concepts_any"); v != "" {
		for _, s := range strings.Split(v, ",") {
			s = strings.TrimSpace(s)
			if s != "" {
				opts.ConceptsAny = append(opts.ConceptsAny, s)
			}
		}
	}
	if v := q.Get("min_score"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			opts.MinScore = &f
		}
	}
	if v := q.Get("max_score"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			opts.MaxScore = &f
		}
	}
	if v := q.Get("bbox"); v != "" {
		parts := strings.Split(v, ",")
		if len(parts) == 4 {
			f := make([]float64, 4)
			ok := true
			for i, p := range parts {
				n, err := strconv.ParseFloat(strings.TrimSpace(p), 64)
				if err != nil {
					ok = false
					break
				}
				f[i] = n
			}
			if ok {
				opts.Bbox = &ports.Bbox{Lon1: f[0], Lat1: f[1], Lon2: f[2], Lat2: f[3]}
			}
		}
	}
	if v := q.Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			opts.Limit = n
		}
	}

	camps, err := h.listCamps.Execute(r.Context(), opts)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if camps == nil {
		camps = nil // ensure `[]` not `null` below
	}
	// Encode an empty slice as [] not null.
	if len(camps) == 0 {
		_, _ = w.Write([]byte("[]"))
		return
	}
	_ = json.NewEncoder(w).Encode(camps)
}
