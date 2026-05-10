package usecases

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// stubCampReader returns whichever camps were preloaded, ignoring filters
// other than IDs.
type stubCampReader struct {
	camps map[string]*domain.Camp
}

func (s *stubCampReader) Get(_ context.Context, id string) (*domain.Camp, error) {
	return s.camps[id], nil
}
func (s *stubCampReader) ListCamps(_ context.Context, opts ports.ListCampsOptions) ([]*domain.Camp, error) {
	out := make([]*domain.Camp, 0, len(opts.IDs))
	for _, id := range opts.IDs {
		if c, ok := s.camps[id]; ok {
			out = append(out, c)
		}
	}
	return out, nil
}
func (s *stubCampReader) Count(_ context.Context) (int, error) { return len(s.camps), nil }

type stubEtaProvider struct {
	// minutes by destination place text
	minutes map[string]int
	calls   []string // record which IDs were actually called (post-prefilter)
}

func (s *stubEtaProvider) DriveEta(_ context.Context, origin, dest string, _ float64) (*domain.EtaResult, error) {
	if m, ok := s.minutes[dest]; ok {
		src := "stub"
		return &domain.EtaResult{Origin: origin, Dest: dest, Minutes: &m, Source: &src}, nil
	}
	msg := "no path"
	return &domain.EtaResult{Origin: origin, Dest: dest, Error: &msg}, nil
}
func (s *stubEtaProvider) DriveEtaBatch(ctx context.Context, origin string, dests []ports.EtaDest, _ int, _ float64) (map[string]*domain.EtaResult, error) {
	out := make(map[string]*domain.EtaResult, len(dests))
	for _, d := range dests {
		s.calls = append(s.calls, d.ID)
		r, _ := s.DriveEta(ctx, origin, d.Place, 0)
		out[d.ID] = r
	}
	return out, nil
}

type stubGeocoder struct {
	point *domain.GeoPoint
	err   error
}

func (s *stubGeocoder) Lookup(_ context.Context, _ string) (*domain.GeoPoint, error) {
	return s.point, s.err
}

func mkCamp(id, sido, sigungu string, lat, lon *float64) *domain.Camp {
	c := &domain.Camp{
		ID:     id,
		Name:   id + "-name",
		Region: domain.Region{Sido: sido, Sigungu: sigungu},
	}
	if lat != nil && lon != nil {
		c.Geo = &domain.GeoPoint{Lat: *lat, Lon: *lon}
	}
	return c
}

func float64p(v float64) *float64 { return &v }
func intp(v int) *int             { return &v }

func TestPlaceForCamp(t *testing.T) {
	addr := "강원 영월군 김삿갓면 내리계곡로 131-12"
	cases := []struct {
		name string
		camp *domain.Camp
		want string
	}{
		{
			name: "sido+sigungu wins",
			camp: &domain.Camp{ID: "x", Name: "n", Region: domain.Region{Sido: "강원", Sigungu: "영월군"}},
			want: "강원 영월군",
		},
		{
			name: "(미지정) sentinel triggers fallback",
			camp: &domain.Camp{ID: "x", Name: "n", Region: domain.Region{Sido: "(미지정)", Sigungu: "(미지정)"}, Address: &addr},
			want: addr,
		},
		{
			name: "address fallback",
			camp: &domain.Camp{ID: "x", Name: "n", Address: &addr},
			want: addr,
		},
		{
			name: "name fallback",
			camp: &domain.Camp{ID: "x", Name: "캠프-foo"},
			want: "캠프-foo",
		},
		{
			name: "id last-resort",
			camp: &domain.Camp{ID: "id-only"},
			want: "id-only",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			assert.Equal(t, tc.want, placeForCamp(tc.camp))
		})
	}
}

func TestHaversineKm_seoulToBusan(t *testing.T) {
	// Seoul (37.5665, 126.9780) → Busan (35.1796, 129.0756)
	// True great-circle ≈ 325 km — accept ±2km.
	got := haversineKm(37.5665, 126.9780, 35.1796, 129.0756)
	assert.InDelta(t, 325.0, got, 2.0, "got %.2f", got)
}

func TestExecute_prefilterSkipsFarCamps(t *testing.T) {
	// Origin Seoul; one near (Suwon, ~30km) one far (Busan, ~325km).
	// max_minutes=60 → radius = (60/60)*90*1.3 = 117 km. Busan is OUT.
	suwonLat, suwonLon := 37.2636, 127.0286
	busanLat, busanLon := 35.1796, 129.0756
	camps := map[string]*domain.Camp{
		"near": mkCamp("near", "경기", "수원시", &suwonLat, &suwonLon),
		"far":  mkCamp("far", "부산", "해운대구", &busanLat, &busanLon),
	}
	reader := &stubCampReader{camps: camps}
	provider := &stubEtaProvider{minutes: map[string]int{"경기 수원시": 35}}
	geo := &stubGeocoder{point: &domain.GeoPoint{Lat: 37.5665, Lon: 126.9780}}
	uc := NewEtaForFleet(reader, provider, geo)

	resp, err := uc.Execute(context.Background(), "서울역", []string{"near", "far"}, intp(60), 4, 12.0)
	assert.NoError(t, err)
	assert.Equal(t, 2, resp.Checked)
	assert.Equal(t, 1, resp.Prefiltered)
	assert.Equal(t, 1, resp.WithinCount)
	if assert.NotNil(t, resp.RadiusKm) {
		assert.InDelta(t, 117.0, *resp.RadiusKm, 0.1)
	}

	// Provider should have only been called for the near camp.
	assert.ElementsMatch(t, []string{"near"}, provider.calls)

	// Result rows in input order.
	assert.Equal(t, "near", resp.Results[0].ID)
	assert.NotNil(t, resp.Results[0].Minutes)
	assert.Equal(t, 35, *resp.Results[0].Minutes)
	assert.True(t, resp.Results[0].Within)

	assert.Equal(t, "far", resp.Results[1].ID)
	assert.Nil(t, resp.Results[1].Minutes)
	if assert.NotNil(t, resp.Results[1].Source) {
		assert.Equal(t, "prefilter", *resp.Results[1].Source)
	}
	assert.False(t, resp.Results[1].Within)
}

func TestExecute_noGeocoder_skipsPrefilter(t *testing.T) {
	// Same input as above, but no geocoder → no haversine pre-filter.
	// Both camps should be sent to provider.
	suwonLat, suwonLon := 37.2636, 127.0286
	busanLat, busanLon := 35.1796, 129.0756
	camps := map[string]*domain.Camp{
		"near": mkCamp("near", "경기", "수원시", &suwonLat, &suwonLon),
		"far":  mkCamp("far", "부산", "해운대구", &busanLat, &busanLon),
	}
	reader := &stubCampReader{camps: camps}
	provider := &stubEtaProvider{minutes: map[string]int{"경기 수원시": 35, "부산 해운대구": 410}}
	uc := NewEtaForFleet(reader, provider, nil)

	resp, err := uc.Execute(context.Background(), "서울역", []string{"near", "far"}, intp(60), 4, 12.0)
	assert.NoError(t, err)
	assert.Equal(t, 0, resp.Prefiltered)
	assert.Nil(t, resp.RadiusKm)
	assert.ElementsMatch(t, []string{"near", "far"}, provider.calls)

	// "far" is ETA 410 > max_minutes 60 → within=false but minutes IS set.
	assert.Equal(t, "far", resp.Results[1].ID)
	assert.Equal(t, 410, *resp.Results[1].Minutes)
	assert.False(t, resp.Results[1].Within)
}

func TestExecute_noMaxMinutes_allWithin(t *testing.T) {
	suwonLat, suwonLon := 37.2636, 127.0286
	camps := map[string]*domain.Camp{
		"a": mkCamp("a", "경기", "수원시", &suwonLat, &suwonLon),
	}
	reader := &stubCampReader{camps: camps}
	provider := &stubEtaProvider{minutes: map[string]int{"경기 수원시": 35}}
	uc := NewEtaForFleet(reader, provider, nil)

	resp, err := uc.Execute(context.Background(), "서울역", []string{"a"}, nil, 4, 12.0)
	assert.NoError(t, err)
	assert.Equal(t, 1, resp.WithinCount, "max_minutes=nil → all returned ETAs are within")
	assert.True(t, resp.Results[0].Within)
}

func TestExecute_unknownCampID_skippedSilently(t *testing.T) {
	reader := &stubCampReader{camps: map[string]*domain.Camp{}}
	provider := &stubEtaProvider{minutes: map[string]int{}}
	uc := NewEtaForFleet(reader, provider, nil)

	resp, err := uc.Execute(context.Background(), "서울역", []string{"missing"}, nil, 4, 12.0)
	assert.NoError(t, err)
	// Python's behavior: missing camp_id → not in raw → result row with
	// error="no place name", within=false. We match that.
	assert.Equal(t, 1, resp.Checked)
	assert.Equal(t, 0, resp.WithinCount)
	if assert.NotNil(t, resp.Results[0].Error) {
		assert.Equal(t, "no place name", *resp.Results[0].Error)
	}
}
