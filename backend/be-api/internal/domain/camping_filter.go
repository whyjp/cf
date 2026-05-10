// IsCampingFacility predicate — 1:1 port of `domain.camping_filter`.
//
// User directive 2026-05-10: "땡큐의 캠핑장외 데이터는 로드하지 않는다."
// Extended to all sources at the read API: a camp is surfaced in /sites only
// if at least one of its type/category/location-type tokens is a recognised
// CAMPING token. Pure pension / bungalow / unknown-only records are dropped.
//
// Token vocabulary
//   - camfit Camp.types carries English codes (autoCamping, pension, glamping,
//     caravan, bungalow, rental, carCamping, experience, trailer)
//   - txcp Camp.types carries Korean labels (오토캠핑, 펜션, 글램핑, 카라반,
//     피크닉, 체험) AND raw txcp BB### codes for unknown taxonomy entries
//
// Rule
//
//	INCLUDE if `types` (and `location_types`) contains ANY token in
//	CAMPING_TOKENS. EXCLUDE otherwise.
package domain

// CampingTokens marks a camp as a *camping* facility. Mix of camfit English
// codes, txcp Korean labels, and raw txcp BB### codes so the predicate works
// on any Camp regardless of source.
var CampingTokens = map[string]struct{}{
	// camfit English codes
	"autoCamping": {}, "glamping": {}, "caravan": {},
	"carCamping": {}, "trailer": {}, "experience": {},
	// txcp Korean labels (the ingest already maps known BB### → Korean)
	"오토캠핑": {}, "글램핑": {}, "카라반": {}, "피크닉": {}, "차박": {}, "체험": {}, "트레일러": {},
	// raw txcp BB### codes (defensive — only the explicitly-camping ones)
	"BB000": {}, "BB001": {}, "BB002": {}, "BB006": {},
}

// IsCampingFacility returns true iff the camp has at least one recognised
// camping token in either Types or LocationTypes.
func IsCampingFacility(c *Camp) bool {
	if c == nil {
		return false
	}
	for _, t := range c.Types {
		if _, ok := CampingTokens[t]; ok {
			return true
		}
	}
	for _, t := range c.LocationTypes {
		if _, ok := CampingTokens[t]; ok {
			return true
		}
	}
	return false
}
