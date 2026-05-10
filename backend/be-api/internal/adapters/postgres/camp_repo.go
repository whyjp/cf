// CampRepo — pgx port of `adapters.postgres.camp_repo.PostgresCampReader`.
//
// SQL is a 1:1 translation of the Python source: same tables, same ordering,
// same per-row enrichment (descriptions / types / facilities / hashtags /
// location_types / collections / medias). Cross-validation against the
// Python /sites endpoint covers correctness end-to-end.
package postgres

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/whyjp/cf/be-api/internal/domain"
	"github.com/whyjp/cf/be-api/internal/ports"
)

// listFields mirrors `_LIST_FIELDS` in the Python source, but uses positional
// pgx scan order ($-placeholders). Keep field order identical.
const listFields = "id, name, sido, sigungu, address, lat, lon, brief, location_brief, contact, " +
	"price_start_from, price_end_to, num_of_reviews, num_of_viewed, bookmark_count, " +
	"url, source"

// listFieldNames duplicates listFields as an []string for prefixing with
// the table alias when building the dynamic SELECT.
var listFieldNames = []string{
	"id", "name", "sido", "sigungu", "address", "lat", "lon",
	"brief", "location_brief", "contact",
	"price_start_from", "price_end_to",
	"num_of_reviews", "num_of_viewed", "bookmark_count",
	"url", "source",
}

// CampRepo implements ports.CampReader on top of pgxpool.
type CampRepo struct {
	pool *pgxpool.Pool
}

// Compile-time assertion: CampRepo implements ports.CampReader.
var _ ports.CampReader = (*CampRepo)(nil)

// NewCampRepo constructs a CampRepo from an existing pgxpool.
func NewCampRepo(pool *pgxpool.Pool) *CampRepo {
	return &CampRepo{pool: pool}
}

// campRow is the in-memory shape we scan into from `camps`.
// Pointer fields = nullable columns.
type campRow struct {
	ID             string
	Name           string
	Sido           *string
	Sigungu        *string
	Address        *string
	Lat            *float64
	Lon            *float64
	Brief          *string
	LocationBrief  *string
	Contact        *string
	PriceStartFrom *int
	PriceEndTo     *int
	NumOfReviews   *int
	NumOfViewed    *int
	BookmarkCount  *int
	URL            *string
	Source         *string
}

// Get fetches a single camp by id. Returns *domain.CampNotFound if missing.
func (r *CampRepo) Get(ctx context.Context, campID string) (*domain.Camp, error) {
	conn, err := r.pool.Acquire(ctx)
	if err != nil {
		return nil, err
	}
	defer conn.Release()

	row, err := scanCampRow(conn.QueryRow(ctx,
		"SELECT "+listFields+" FROM camps WHERE id = $1", campID))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, &domain.CampNotFound{CampID: campID}
		}
		return nil, err
	}
	return r.enrich(ctx, conn.Conn(), row)
}

// Count returns total camps in the database.
func (r *CampRepo) Count(ctx context.Context) (int, error) {
	var n int
	if err := r.pool.QueryRow(ctx, "SELECT count(*) FROM camps").Scan(&n); err != nil {
		return 0, err
	}
	return n, nil
}

// ListCamps is the workhorse for /sites. SQL is built dynamically from opts —
// same WHERE/JOIN strategy as the Python source.
//
//   - sido / sigungu: simple equality
//   - bbox: lon BETWEEN AND lat BETWEEN (normalised so order doesn't matter)
//   - ids: ANY($N)
//   - concept (AND): one JOIN per concept, each binding `agg_<i>.concept_id`
//     and optionally `final_score >= / <=`
//   - concepts_any (OR): single JOIN with `agg_any.concept_id = ANY($N)`
//
// Limit defaults to 10000 if zero (matches P5 cap lift).
func (r *CampRepo) ListCamps(ctx context.Context, opts ports.ListCampsOptions) ([]*domain.Camp, error) {
	conn, err := r.pool.Acquire(ctx)
	if err != nil {
		return nil, err
	}
	defer conn.Release()

	var (
		wh     []string
		params []any
	)
	pn := 0
	bind := func(v any) string {
		pn++
		params = append(params, v)
		return fmt.Sprintf("$%d", pn)
	}

	if opts.Sido != nil && *opts.Sido != "" {
		wh = append(wh, "c.sido = "+bind(*opts.Sido))
	}
	if opts.Sigungu != nil && *opts.Sigungu != "" {
		wh = append(wh, "c.sigungu = "+bind(*opts.Sigungu))
	}
	if opts.Bbox != nil {
		bb := opts.Bbox
		lon1, lon2 := minF(bb.Lon1, bb.Lon2), maxF(bb.Lon1, bb.Lon2)
		lat1, lat2 := minF(bb.Lat1, bb.Lat2), maxF(bb.Lat1, bb.Lat2)
		wh = append(wh, "c.lon BETWEEN "+bind(lon1)+" AND "+bind(lon2)+
			" AND c.lat BETWEEN "+bind(lat1)+" AND "+bind(lat2))
	}
	if len(opts.IDs) > 0 {
		wh = append(wh, "c.id = ANY("+bind(opts.IDs)+")")
	}

	// Build SELECT prefix
	cols := make([]string, len(listFieldNames))
	for i, f := range listFieldNames {
		cols[i] = "c." + f
	}
	sql := "SELECT " + strings.Join(cols, ", ") + " FROM camps c "

	// AND-semantics over concept[]
	if len(opts.Concept) > 0 {
		for i, cidFilter := range opts.Concept {
			alias := fmt.Sprintf("agg_%d", i)
			sql += " JOIN camp_concept_aggregated " + alias +
				" ON " + alias + ".camp_id=c.id AND " + alias + ".concept_id=" + bind(cidFilter) + " "
			if opts.MinScore != nil {
				wh = append(wh, alias+".final_score >= "+bind(*opts.MinScore))
			}
			if opts.MaxScore != nil {
				wh = append(wh, alias+".final_score <= "+bind(*opts.MaxScore))
			}
		}
	}

	// OR-semantics over concepts_any
	if len(opts.ConceptsAny) > 0 {
		sql += " JOIN camp_concept_aggregated agg_any ON agg_any.camp_id=c.id "
		wh = append(wh, "agg_any.concept_id = ANY("+bind(opts.ConceptsAny)+")")
		if opts.MinScore != nil {
			wh = append(wh, "agg_any.final_score >= "+bind(*opts.MinScore))
		}
		if opts.MaxScore != nil {
			wh = append(wh, "agg_any.final_score <= "+bind(*opts.MaxScore))
		}
	}

	if len(wh) > 0 {
		sql += " WHERE " + strings.Join(wh, " AND ")
	}

	limit := opts.Limit
	if limit <= 0 {
		limit = 10000
	}
	sql += " LIMIT " + bind(limit)

	rows, err := conn.Query(ctx, sql, params...)
	if err != nil {
		return nil, err
	}
	var bare []campRow
	for rows.Next() {
		row, err := scanCampRowFromRows(rows)
		if err != nil {
			rows.Close()
			return nil, err
		}
		bare = append(bare, row)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	out := make([]*domain.Camp, 0, len(bare))
	for _, row := range bare {
		camp, err := r.enrich(ctx, conn.Conn(), row)
		if err != nil {
			return nil, err
		}
		out = append(out, camp)
	}
	return out, nil
}

// enrich fetches the per-camp child rows (description / types / facilities /
// hashtags / location_types / collections / medias) and assembles a domain
// Camp. Same logic / ordering as the Python `_enrich`.
func (r *CampRepo) enrich(ctx context.Context, conn *pgx.Conn, row campRow) (*domain.Camp, error) {
	cid := row.ID

	// description
	var description *string
	if err := conn.QueryRow(ctx,
		"SELECT description FROM camp_descriptions WHERE camp_id=$1", cid).Scan(&description); err != nil {
		if !errors.Is(err, pgx.ErrNoRows) {
			return nil, err
		}
	}

	listOf := func(table, col string) ([]string, error) {
		rs, err := conn.Query(ctx,
			"SELECT "+col+" FROM "+table+" WHERE camp_id=$1 ORDER BY "+col, cid)
		if err != nil {
			return nil, err
		}
		defer rs.Close()
		out := []string{}
		for rs.Next() {
			var v string
			if err := rs.Scan(&v); err != nil {
				return nil, err
			}
			out = append(out, v)
		}
		return out, rs.Err()
	}

	types, err := listOf("camp_types", "type")
	if err != nil {
		return nil, err
	}

	// facilities split by is_additional
	facRows, err := conn.Query(ctx,
		"SELECT facility, is_additional FROM camp_facilities WHERE camp_id=$1 ORDER BY facility", cid)
	if err != nil {
		return nil, err
	}
	facs := []string{}
	addl := []string{}
	for facRows.Next() {
		var f string
		var isAdd bool
		if err := facRows.Scan(&f, &isAdd); err != nil {
			facRows.Close()
			return nil, err
		}
		if isAdd {
			addl = append(addl, f)
		} else {
			facs = append(facs, f)
		}
	}
	facRows.Close()
	if err := facRows.Err(); err != nil {
		return nil, err
	}

	hashtags, err := listOf("camp_hashtags", "hashtag")
	if err != nil {
		return nil, err
	}
	locTypes, err := listOf("camp_location_types", "location_type")
	if err != nil {
		return nil, err
	}
	collections, err := listOf("camp_collections", "collection_name")
	if err != nil {
		return nil, err
	}

	// medias / photos
	mRows, err := conn.Query(ctx,
		"SELECT idx, url, thumb_url, w, h FROM camp_medias WHERE camp_id=$1 ORDER BY idx", cid)
	if err != nil {
		return nil, err
	}
	photos := []domain.Photo{}
	for mRows.Next() {
		var idx int
		var url string
		var thumb *string
		var w, h *int
		if err := mRows.Scan(&idx, &url, &thumb, &w, &h); err != nil {
			mRows.Close()
			return nil, err
		}
		photos = append(photos, domain.Photo{
			URL: url, ThumbURL: thumb, Width: w, Height: h,
		})
	}
	mRows.Close()
	if err := mRows.Err(); err != nil {
		return nil, err
	}

	// geo: only set if both lat/lon present
	var geo *domain.GeoPoint
	if row.Lat != nil && row.Lon != nil {
		geo = &domain.GeoPoint{Lat: *row.Lat, Lon: *row.Lon}
	}

	// Region: Python falls back to "(미지정)" when sido/sigungu is NULL.
	region := domain.Region{
		Sido:    nzs(row.Sido, "(미지정)"),
		Sigungu: nzs(row.Sigungu, "(미지정)"),
	}

	camp := &domain.Camp{
		ID:                   cid,
		Name:                 row.Name,
		Region:               region,
		Address:              row.Address,
		Geo:                  geo,
		Types:                types,
		Facilities:           facs,
		AdditionalFacilities: addl,
		LocationTypes:        locTypes,
		Hashtags:             hashtags,
		Collections:          collections,
		Description:          description,
		Brief:                row.Brief,
		LocationBrief:        row.LocationBrief,
		Contact:              row.Contact,
		PriceStartFrom:       row.PriceStartFrom,
		PriceEndTo:           row.PriceEndTo,
		NumOfReviews:         nzi(row.NumOfReviews, 0),
		NumOfViewed:          nzi(row.NumOfViewed, 0),
		BookmarkCount:        nzi(row.BookmarkCount, 0),
		URL:                  row.URL,
		Source:               nzs(row.Source, "camfit"),
		Photos:               photos,
	}
	return camp, nil
}

// scanCampRow scans a single camps row from QueryRow.
func scanCampRow(row pgx.Row) (campRow, error) {
	var r campRow
	err := row.Scan(
		&r.ID, &r.Name, &r.Sido, &r.Sigungu, &r.Address, &r.Lat, &r.Lon,
		&r.Brief, &r.LocationBrief, &r.Contact,
		&r.PriceStartFrom, &r.PriceEndTo,
		&r.NumOfReviews, &r.NumOfViewed, &r.BookmarkCount,
		&r.URL, &r.Source,
	)
	return r, err
}

// scanCampRowFromRows scans a single camps row from Rows.Scan.
func scanCampRowFromRows(rows pgx.Rows) (campRow, error) {
	var r campRow
	err := rows.Scan(
		&r.ID, &r.Name, &r.Sido, &r.Sigungu, &r.Address, &r.Lat, &r.Lon,
		&r.Brief, &r.LocationBrief, &r.Contact,
		&r.PriceStartFrom, &r.PriceEndTo,
		&r.NumOfReviews, &r.NumOfViewed, &r.BookmarkCount,
		&r.URL, &r.Source,
	)
	return r, err
}

// helpers ────────────────────────────────────────────────────────────────────

func nzs(p *string, dflt string) string {
	if p == nil {
		return dflt
	}
	return *p
}

func nzi(p *int, dflt int) int {
	if p == nil {
		return dflt
	}
	return *p
}

func minF(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

func maxF(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
