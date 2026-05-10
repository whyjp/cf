// Geocoder port — mirrors Python `cf_be_api.ports.geocode.Geocoder`.
//
// Returns nil for unresolvable addresses rather than error so the use-case
// can choose to surface a tailored message ("could not resolve origin
// '강남역'") without unwrapping ErrEmptyPath.
package ports

import (
	"context"

	"github.com/whyjp/cf/be-api-go/internal/domain"
)

// Geocoder resolves a Korean place name (POI / address / station / landmark)
// to a (lat, lon) pair.
type Geocoder interface {
	// Lookup returns nil + nil error when the address cannot be resolved.
	// Network or upstream failures DO surface as a non-nil error so the
	// use-case can distinguish "can't resolve" from "outage".
	Lookup(ctx context.Context, address string) (*domain.GeoPoint, error)
}
