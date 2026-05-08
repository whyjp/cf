// Package duration shapes route results for STDOUT. Default is the integer
// minute count on a single line; --json flips to a stable, machine-parseable
// envelope that preserves the user's original start/end strings (NFR-2).
package duration

import (
	"encoding/json"
	"fmt"

	"github.com/whyjp/etago/internal/parse"
	"github.com/whyjp/etago/internal/route"
)

// Options configure a single Format call.
type Options struct {
	JSON bool
}

// jsonEnvelope is the on-the-wire shape for --json. The field order is
// fixed so downstream parsers can rely on it for snapshot tests.
type jsonEnvelope struct {
	Start       string `json:"start"`
	End         string `json:"end"`
	DurationMin int    `json:"duration_min"`
	Source      string `json:"source"`
}

// Format produces the STDOUT line. It does not append a newline; the caller
// (cmd/etago) prints with fmt.Println so trailing-newline behaviour stays
// in one place.
func Format(d route.Duration, in parse.NormalizedInput, opts Options) string {
	if opts.JSON {
		b, _ := json.Marshal(jsonEnvelope{
			Start:       in.Start,
			End:         in.End,
			DurationMin: d.Min,
			Source:      d.Source,
		})
		return string(b)
	}
	return fmt.Sprintf("%d min", d.Min)
}
