// Package domain mirrors the Python be-api Pydantic models 1:1.
//
// Field names use snake_case JSON tags to match the Python `Camp.model_dump()`
// shape — the cross-validation tests in tests/cross_validation rely on the
// Go and Python /sites responses returning identical ID sets, and the D-4
// fixture comparison will demand byte-equal JSON for the projection.
package domain

// Region mirrors `domain.models.Region` (sido/sigungu administrative split).
type Region struct {
	Sido    string `json:"sido"`
	Sigungu string `json:"sigungu"`
}

// GeoPoint mirrors `domain.models.GeoPoint`. Bounds (lat 33–39, lon 124–132)
// are NOT enforced here — Pydantic enforces on construction; in Go the data
// arrives from Postgres already validated, and adapters drop invalid values
// to nil rather than rejecting the whole row.
type GeoPoint struct {
	Lat float64 `json:"lat"`
	Lon float64 `json:"lon"`
}

// Photo mirrors `domain.models.Photo`. Pointer fields = Pydantic Optional[T].
type Photo struct {
	URL      string `json:"url"`
	ThumbURL *string `json:"thumb_url"`
	Width    *int    `json:"width"`
	Height   *int    `json:"height"`
}

// Camp mirrors `domain.models.Camp`. JSON tags match Pydantic snake_case
// `model_dump()` output exactly — DO NOT change without updating the D-4
// fixture diff.
//
// Slice/map fields are encoded as empty `[]`/`{}` in Pydantic when unset; we
// initialise them to non-nil in the adapters so json.Marshal emits `[]` not
// `null`.
type Camp struct {
	ID                   string   `json:"id"`
	Name                 string   `json:"name"`
	Region               Region   `json:"region"`
	Address              *string  `json:"address"`
	Geo                  *GeoPoint `json:"geo"`
	Types                []string `json:"types"`
	Facilities           []string `json:"facilities"`
	AdditionalFacilities []string `json:"additional_facilities"`
	LocationTypes        []string `json:"location_types"`
	Hashtags             []string `json:"hashtags"`
	Collections          []string `json:"collections"`
	Description          *string  `json:"description"`
	Brief                *string  `json:"brief"`
	LocationBrief        *string  `json:"location_brief"`
	Contact              *string  `json:"contact"`
	PriceStartFrom       *int     `json:"price_start_from"`
	PriceEndTo           *int     `json:"price_end_to"`
	NumOfReviews         int      `json:"num_of_reviews"`
	NumOfViewed          int      `json:"num_of_viewed"`
	BookmarkCount        int      `json:"bookmark_count"`
	URL                  *string  `json:"url"`
	Source               string   `json:"source"`
	Photos               []Photo  `json:"photos"`
}

// Review mirrors `domain.models.Review`.
type Review struct {
	ID              string   `json:"id"`
	CampID          string   `json:"camp_id"`
	UserNick        *string  `json:"user_nick"`
	Season          *string  `json:"season"`
	UserType        *string  `json:"user_type"`
	NumOfDays       *int     `json:"num_of_days"`
	Score           *float64 `json:"score"`
	Text            string   `json:"text"`
	IsClean         *bool    `json:"is_clean"`
	IsKind          *bool    `json:"is_kind"`
	IsManner        *bool    `json:"is_manner"`
	IsConvenient    *bool    `json:"is_convenient"`
	ReviewTimestamp *int64   `json:"review_timestamp"`
	Medias          []string `json:"medias"`
}

// Concept mirrors `domain.models.Concept`. Source ∈ {hashtag, facility, manual, ngram}.
type Concept struct {
	ID          string  `json:"id"`
	Name        string  `json:"name"`
	Source      string  `json:"source"`
	Category    *string `json:"category"`
	Description *string `json:"description"`
	IsAxis      bool    `json:"is_axis"`
	SeedTerm    *string `json:"seed_term"`
}

// CampConcept mirrors `domain.models.CampConcept`. Score range [-3.0, +3.0]
// (theoretical envelope ±2.2 from camp_concept_aggregated weighted-sum).
type CampConcept struct {
	CampID    string  `json:"camp_id"`
	ConceptID string  `json:"concept_id"`
	Score     float64 `json:"score"`
}

// Theme mirrors `domain.models.Theme`.
type Theme struct {
	ID          string    `json:"id"`
	Label       string    `json:"label"`
	Centroid    []float64 `json:"centroid"`
	MemberCount int       `json:"member_count"`
	ManualLabel *string   `json:"manual_label"`
}

// EtaResult mirrors `domain.models.EtaResult` (D-5 will populate).
type EtaResult struct {
	Origin  string  `json:"origin"`
	Dest    string  `json:"dest"`
	Minutes *int    `json:"minutes"`
	Source  *string `json:"source"`
	Error   *string `json:"error"`
}

// Mark mirrors `domain.models.Mark`. Level ∈ {bib, recommended, notable, exceptional}.
// Score envelope ±10 (camp_review_signals SUM × intensifier).
type Mark struct {
	CampID   string  `json:"camp_id"`
	Axis     string  `json:"axis"`
	Level    string  `json:"level"`
	Score    float64 `json:"score"`
	Evidence *string `json:"evidence"`
}
