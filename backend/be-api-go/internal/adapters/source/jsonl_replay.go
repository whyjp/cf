// Package source implements ports.SourceReader against on-disk replay data.
//
// Two formats supported:
//
//  1. JSONL — one Camp per line, used by the Go-native ingest path (D-5+).
//  2. JSON arrays in `camps_dedup.json` — the legacy camfit replay shape used
//     by the Python `LocalReplaySource`. Detected by file extension.
//
// The Python adapter has two distinct roles (summary vs detail per-id JSON
// files); for D-2 we cover IterSummaries since that's what the read path
// uses. GetDetail / IterReviews / IterFilters are stubbed with the right
// shape for D-3+ to fill in (per-id detail files & review files).
package source

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// JsonlSource reads Camp records from either a single .jsonl file or a
// directory containing `camps_dedup.json` (legacy camfit shape).
type JsonlSource struct {
	path string // file or directory
	name string
}

// NewJsonlSource creates a source from a path. The path may be either a
// .jsonl file or a directory containing camps_dedup.json.
func NewJsonlSource(path string) *JsonlSource {
	name := "jsonl-replay"
	st, err := os.Stat(path)
	if err == nil && st.IsDir() {
		name = "local-replay"
	}
	return &JsonlSource{path: path, name: name}
}

// Name returns the source's identifier.
func (s *JsonlSource) Name() string { return s.name }

// IterSummaries yields Camp records from disk. Errors during iteration are
// posted to the err channel; the camp channel is closed once iteration ends.
func (s *JsonlSource) IterSummaries(ctx context.Context) (<-chan *domain.Camp, <-chan error) {
	out := make(chan *domain.Camp)
	errs := make(chan error, 1)

	go func() {
		defer close(out)
		defer close(errs)

		st, err := os.Stat(s.path)
		if err != nil {
			errs <- &domain.SourceUnavailable{Msg: err.Error()}
			return
		}

		if st.IsDir() {
			s.iterDedupDir(ctx, out, errs)
			return
		}
		s.iterJsonlFile(ctx, out, errs)
	}()

	return out, errs
}

// iterJsonlFile scans a JSONL file line-by-line, decoding each into Camp.
func (s *JsonlSource) iterJsonlFile(ctx context.Context, out chan<- *domain.Camp, errs chan<- error) {
	f, err := os.Open(s.path)
	if err != nil {
		errs <- &domain.SourceUnavailable{Msg: err.Error()}
		return
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	// 1 MiB buffer, 16 MiB cap — Camp records can include long descriptions.
	scanner.Buffer(make([]byte, 1<<20), 1<<24)

	lineNo := 0
	for scanner.Scan() {
		lineNo++
		select {
		case <-ctx.Done():
			errs <- ctx.Err()
			return
		default:
		}
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var camp domain.Camp
		if err := json.Unmarshal([]byte(line), &camp); err != nil {
			errs <- fmt.Errorf("line %d: %w", lineNo, err)
			return
		}
		// Ensure non-nil slices for Pydantic shape parity.
		ensureSlices(&camp)
		select {
		case <-ctx.Done():
			errs <- ctx.Err()
			return
		case out <- &camp:
		}
	}
	if err := scanner.Err(); err != nil {
		errs <- err
	}
}

// iterDedupDir handles a directory that contains `camps_dedup.json`. The
// dedup file is a JSON array of raw camfit summaries — we coerce the few
// fields the read API needs (id, name, region, types).
func (s *JsonlSource) iterDedupDir(ctx context.Context, out chan<- *domain.Camp, errs chan<- error) {
	dedupPath := filepath.Join(s.path, "camps_dedup.json")
	data, err := os.ReadFile(dedupPath)
	if err != nil {
		errs <- &domain.SourceUnavailable{Msg: err.Error()}
		return
	}
	var raw []map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		errs <- err
		return
	}
	for _, r := range raw {
		select {
		case <-ctx.Done():
			errs <- ctx.Err()
			return
		default:
		}
		camp := summaryFromRaw(r)
		if camp == nil {
			continue
		}
		select {
		case <-ctx.Done():
			errs <- ctx.Err()
			return
		case out <- camp:
		}
	}
}

// summaryFromRaw mirrors `LocalReplaySource._summary` — coerce the camfit raw
// dict into a Camp summary. Returns nil if id is missing.
func summaryFromRaw(raw map[string]any) *domain.Camp {
	id := str(raw, "id")
	if id == "" {
		id = str(raw, "_id")
	}
	if id == "" {
		return nil
	}
	name := str(raw, "name")
	if name == "" {
		name = "(이름 미상)"
	}
	city := str(raw, "city")
	if city == "" {
		city = "(미지정)"
	}
	major := str(raw, "major")
	if major == "" {
		major = "(미지정)"
	}
	urlS := str(raw, "url")
	if urlS == "" {
		urlS = fmt.Sprintf("https://camfit.co.kr/camp/%s", id)
	}
	urlPtr := &urlS

	types := []string{}
	for _, t := range strings.Split(str(raw, "type"), ",") {
		t = strings.TrimSpace(t)
		if t != "" {
			types = append(types, t)
		}
	}
	collections := []string{}
	if c, ok := raw["_collections"].([]any); ok {
		for _, v := range c {
			if s, ok := v.(string); ok {
				collections = append(collections, s)
			}
		}
	}

	camp := &domain.Camp{
		ID:          id,
		Name:        name,
		Region:      domain.Region{Sido: city, Sigungu: major},
		URL:         urlPtr,
		Types:       types,
		Collections: collections,
		Source:      "camfit",
	}
	ensureSlices(camp)
	return camp
}

// GetDetail returns nil — D-3+ will read from per-id detail files.
func (s *JsonlSource) GetDetail(_ context.Context, _ string) (*domain.Camp, error) {
	return nil, errors.New("jsonl_replay.GetDetail: not implemented (D-3+)")
}

// IterReviews returns an immediately-closed empty stream — D-3+ will
// implement once review pipelines move to Go.
func (s *JsonlSource) IterReviews(_ context.Context, _ string, _ string) (<-chan *domain.Review, <-chan error) {
	out := make(chan *domain.Review)
	errs := make(chan error, 1)
	close(out)
	close(errs)
	return out, errs
}

// IterFilters returns an immediately-closed empty stream — local-replay does
// not surface camfit's native taxonomy. Same behavior as Python.
func (s *JsonlSource) IterFilters(_ context.Context) (<-chan ports.FilterEntry, <-chan error) {
	out := make(chan ports.FilterEntry)
	errs := make(chan error, 1)
	close(out)
	close(errs)
	return out, errs
}

// Compile-time assertion: JsonlSource implements ports.SourceReader.
var _ ports.SourceReader = (*JsonlSource)(nil)

// helpers ────────────────────────────────────────────────────────────────────

func str(m map[string]any, k string) string {
	if v, ok := m[k]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}

func ensureSlices(c *domain.Camp) {
	if c.Types == nil {
		c.Types = []string{}
	}
	if c.Facilities == nil {
		c.Facilities = []string{}
	}
	if c.AdditionalFacilities == nil {
		c.AdditionalFacilities = []string{}
	}
	if c.LocationTypes == nil {
		c.LocationTypes = []string{}
	}
	if c.Hashtags == nil {
		c.Hashtags = []string{}
	}
	if c.Collections == nil {
		c.Collections = []string{}
	}
	if c.Photos == nil {
		c.Photos = []domain.Photo{}
	}
}
