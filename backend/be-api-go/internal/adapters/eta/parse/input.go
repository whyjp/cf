// Package parse normalizes user-supplied natural-language place names into
// the input shape consumed by route providers. It enforces three properties
// the rest of the pipeline relies on: non-empty, UTF-8 bounded length, and
// non-coordinate (CLI accepts place names only).
package parse

import (
	"errors"
	"regexp"
	"strings"
	"unicode/utf8"
)

// MaxRunes is the upper bound on a single input field, in runes.
// 256 was chosen to comfortably fit Korean place names including
// detailed address suffixes while keeping URL query strings short.
const MaxRunes = 256

// coordRE matches "lat,lng" decimal pairs. Coordinates are rejected because
// the CLI is intentionally a place-name interface (intent §c, D-1).
var coordRE = regexp.MustCompile(`^-?\d+(?:\.\d+)?,\s*-?\d+(?:\.\d+)?$`)

// Sentinel errors. Callers distinguish them via errors.Is to map exit codes.
var (
	ErrEmpty           = errors.New("start and end must be non-empty")
	ErrCoordNotAllowed = errors.New("coordinate input is not allowed; use a place name")
	ErrTooLong         = errors.New("input exceeds 256 runes")
)

// NormalizedInput is the validated pair handed to route providers.
// Both fields preserve the user's original text (NFR-2 priority-fidelity);
// only leading/trailing whitespace is stripped.
type NormalizedInput struct {
	Start string
	End   string
}

// NormalizeInputs trims whitespace, rejects empty/coordinate/over-length input,
// and otherwise returns the inputs verbatim so providers see exactly what the
// user typed.
func NormalizeInputs(start, end string) (NormalizedInput, error) {
	s := strings.TrimSpace(start)
	e := strings.TrimSpace(end)
	if s == "" || e == "" {
		return NormalizedInput{}, ErrEmpty
	}
	if coordRE.MatchString(s) || coordRE.MatchString(e) {
		return NormalizedInput{}, ErrCoordNotAllowed
	}
	if utf8.RuneCountInString(s) > MaxRunes || utf8.RuneCountInString(e) > MaxRunes {
		return NormalizedInput{}, ErrTooLong
	}
	return NormalizedInput{Start: s, End: e}, nil
}
