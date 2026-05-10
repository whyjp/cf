// EtaForFleet — 1:1 port of `cf_be_api.usecases.eta_for_fleet.EtaForFleet`.
//
// Compute drive ETA from a single origin to many camps.
//
//  1. Hydrate camps via CampReader.ListCamps(ids=camp_ids).
//  2. (Optional) When max_minutes is set and the origin can be geocoded,
//     pre-filter by haversine radius = (max_minutes / 60) × 90 km/h × 1.3.
//     Camps outside the radius are returned as {minutes: nil, source:
//     "prefilter", error: "~Xkm > Ykm radius", within: false} without
//     paying for a driving-ETA call.
//  3. For each remaining camp: compute place_for(camp) — prefer
//     "<sido> <sigungu>", fall back to address, name, id.
//  4. Call EtaProvider.DriveEtaBatch with the (id, place) pairs.
//  5. Compose result list in the input order; "within" = ETA <= max_minutes.
package usecases

import (
	"context"
	"fmt"
	"math"
	"strings"

	"github.com/whyjp/cf/be-api/internal/domain"
	"github.com/whyjp/cf/be-api/internal/ports"
)

// EtaForFleet wires the use-case dependencies. Geocoder is OPTIONAL — when
// nil, the haversine pre-filter is skipped (matching Python).
type EtaForFleet struct {
	camps    ports.CampReader
	eta      ports.EtaProvider
	geocoder ports.Geocoder
}

// NewEtaForFleet constructs an EtaForFleet.
func NewEtaForFleet(camps ports.CampReader, eta ports.EtaProvider, geocoder ports.Geocoder) *EtaForFleet {
	return &EtaForFleet{camps: camps, eta: eta, geocoder: geocoder}
}

// EtaForFleetItem is one row in the response, matching Python's per-camp
// dict shape exactly. JSON tags are snake_case to byte-match the Python
// FastAPI response (cross-validation in tests/cross_validation depends on it).
type EtaForFleetItem struct {
	ID      string  `json:"id"`
	Minutes *int    `json:"minutes"`
	Source  *string `json:"source"`
	Error   *string `json:"error"`
	Within  bool    `json:"within"`
	Place   *string `json:"place"`
}

// EtaForFleetResponse is the top-level response shape.
type EtaForFleetResponse struct {
	Origin       string             `json:"origin"`
	MaxMinutes   *int               `json:"max_minutes"`
	Checked      int                `json:"checked"`
	WithinCount  int                `json:"within_count"`
	Prefiltered  int                `json:"prefiltered"`
	RadiusKm     *float64           `json:"radius_km"`
	Results      []EtaForFleetItem  `json:"results"`
}

// Korean expressway-skewed avg + detour safety factor. 90×1.3 = 117 km per
// road-hour. A 2-hour budget → 234 km haversine radius from the origin.
const (
	avgKmh       = 90.0
	detourFactor = 1.3
	earthRadiusK = 6371.0
)

// Execute mirrors `EtaForFleet.execute(origin, camp_ids, *, max_minutes,
// concurrency, timeout_s)`. concurrency / timeoutS default to 4 / 12.0
// when caller passes 0 — same defaults as Python.
func (uc *EtaForFleet) Execute(
	ctx context.Context,
	origin string,
	campIDs []string,
	maxMinutes *int,
	concurrency int,
	timeoutS float64,
) (*EtaForFleetResponse, error) {
	if concurrency <= 0 {
		concurrency = 4
	}
	if timeoutS <= 0 {
		timeoutS = 12.0
	}

	camps, err := uc.camps.ListCamps(ctx, ports.ListCampsOptions{IDs: campIDs, Limit: len(campIDs)})
	if err != nil {
		return nil, fmt.Errorf("list camps: %w", err)
	}
	campsByID := make(map[string]*domain.Camp, len(camps))
	for _, c := range camps {
		campsByID[c.ID] = c
	}

	// Haversine pre-filter — only when max_minutes AND geocoder give us
	// an origin point. Python catches all exceptions on geocode and falls
	// back to "no pre-filter"; we do the same.
	var (
		radiusKm  *float64
		originGeo *domain.GeoPoint
	)
	if maxMinutes != nil && *maxMinutes > 0 && uc.geocoder != nil {
		gp, gerr := uc.geocoder.Lookup(ctx, origin)
		if gerr == nil && gp != nil {
			originGeo = gp
			r := (float64(*maxMinutes) / 60.0) * avgKmh * detourFactor
			radiusKm = &r
		}
	}

	prefiltered := make(map[string]float64) // camp_id → haversine km
	placeFor := make(map[string]string, len(campIDs))
	pairs := make([]ports.EtaDest, 0, len(campIDs))
	for _, cid := range campIDs {
		camp, ok := campsByID[cid]
		if !ok || camp == nil {
			continue
		}
		if radiusKm != nil && originGeo != nil && camp.Geo != nil {
			d := haversineKm(originGeo.Lat, originGeo.Lon, camp.Geo.Lat, camp.Geo.Lon)
			if d > *radiusKm {
				prefiltered[cid] = d
				continue
			}
		}
		place := placeForCamp(camp)
		if place == "" {
			continue
		}
		placeFor[cid] = place
		pairs = append(pairs, ports.EtaDest{ID: cid, Place: place})
	}

	raw, err := uc.eta.DriveEtaBatch(ctx, origin, pairs, concurrency, timeoutS)
	if err != nil {
		return nil, fmt.Errorf("drive eta batch: %w", err)
	}

	results := make([]EtaForFleetItem, 0, len(campIDs))
	within := 0
	for _, cid := range campIDs {
		if d, isPre := prefiltered[cid]; isPre {
			msg := fmt.Sprintf("~%.0fkm > %.0fkm radius", d, *radiusKm)
			src := "prefilter"
			results = append(results, EtaForFleetItem{
				ID:     cid,
				Source: &src,
				Error:  &msg,
				Within: false,
			})
			continue
		}
		r, has := raw[cid]
		if !has {
			msg := "no place name"
			results = append(results, EtaForFleetItem{
				ID:     cid,
				Error:  &msg,
				Within: false,
			})
			continue
		}
		ok := r.Minutes != nil && (maxMinutes == nil || *r.Minutes <= *maxMinutes)
		if ok {
			within++
		}
		var placePtr *string
		if p, hasPlace := placeFor[cid]; hasPlace {
			placePtr = &p
		}
		results = append(results, EtaForFleetItem{
			ID:      cid,
			Minutes: r.Minutes,
			Source:  r.Source,
			Error:   r.Error,
			Within:  ok,
			Place:   placePtr,
		})
	}

	resp := &EtaForFleetResponse{
		Origin:      origin,
		MaxMinutes:  maxMinutes,
		Checked:     len(results),
		WithinCount: within,
		Prefiltered: len(prefiltered),
		Results:     results,
	}
	if radiusKm != nil {
		rounded := math.Round(*radiusKm*10) / 10 // one decimal — matches Python `round(_, 1)`
		resp.RadiusKm = &rounded
	}
	return resp, nil
}

// haversineKm — great-circle distance in km between two lat/lon points.
// Numerically equivalent to the Python implementation (R=6371.0, asin form).
func haversineKm(lat1, lon1, lat2, lon2 float64) float64 {
	p1 := lat1 * math.Pi / 180
	p2 := lat2 * math.Pi / 180
	dp := (lat2 - lat1) * math.Pi / 180
	dl := (lon2 - lon1) * math.Pi / 180
	a := math.Sin(dp/2)*math.Sin(dp/2) +
		math.Cos(p1)*math.Cos(p2)*math.Sin(dl/2)*math.Sin(dl/2)
	return 2 * earthRadiusK * math.Asin(math.Sqrt(a))
}

// placeForCamp picks the best place-name for the geocoder. Mirrors Python's
// `_place_for(camp)` exactly:
//
//  1. "<sido> <sigungu>" if both non-empty AND not the (미지정) sentinel
//  2. camp.address if set
//  3. camp.name if set
//  4. camp.id (last-resort)
func placeForCamp(c *domain.Camp) string {
	sido := strings.TrimSpace(c.Region.Sido)
	sigungu := strings.TrimSpace(c.Region.Sigungu)
	region := strings.TrimSpace(strings.Join(filterEmpty([]string{sido, sigungu}), " "))
	if region != "" && region != "(미지정) (미지정)" && !strings.Contains(region, "(미지정)") {
		return region
	}
	if c.Address != nil && strings.TrimSpace(*c.Address) != "" {
		return strings.TrimSpace(*c.Address)
	}
	if name := strings.TrimSpace(c.Name); name != "" {
		return name
	}
	return c.ID
}

func filterEmpty(in []string) []string {
	out := make([]string, 0, len(in))
	for _, s := range in {
		if s != "" {
			out = append(out, s)
		}
	}
	return out
}
