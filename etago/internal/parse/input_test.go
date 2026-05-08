package parse

import (
	"errors"
	"strings"
	"testing"
)

func TestNormalize_emptyStart_returnsErrEmpty(t *testing.T) {
	_, err := NormalizeInputs("", "수원시청")
	if !errors.Is(err, ErrEmpty) {
		t.Fatalf("want ErrEmpty, got %v", err)
	}
}

func TestNormalize_whitespaceOnly_returnsErrEmpty(t *testing.T) {
	_, err := NormalizeInputs("강남역", "   ")
	if !errors.Is(err, ErrEmpty) {
		t.Fatalf("want ErrEmpty, got %v", err)
	}
}

func TestNormalize_coord_returnsErrCoordNotAllowed(t *testing.T) {
	_, err := NormalizeInputs("37.4979,127.0276", "수원시청")
	if !errors.Is(err, ErrCoordNotAllowed) {
		t.Fatalf("want ErrCoordNotAllowed, got %v", err)
	}
}

func TestNormalize_preservesUTF8(t *testing.T) {
	in, err := NormalizeInputs("강남역 1번 출구", "수원시청")
	if err != nil {
		t.Fatal(err)
	}
	if in.Start != "강남역 1번 출구" {
		t.Errorf("start mutated: %q", in.Start)
	}
	if in.End != "수원시청" {
		t.Errorf("end mutated: %q", in.End)
	}
}

func TestNormalize_trimsOuterWhitespace(t *testing.T) {
	in, _ := NormalizeInputs("  강남역\n", "\t수원시청 ")
	if in.Start != "강남역" || in.End != "수원시청" {
		t.Errorf("trim failed: %+v", in)
	}
}

func TestNormalize_overLength_returnsErrTooLong(t *testing.T) {
	long := strings.Repeat("가", MaxRunes+1)
	_, err := NormalizeInputs(long, "수원시청")
	if !errors.Is(err, ErrTooLong) {
		t.Fatalf("want ErrTooLong, got %v", err)
	}
}

func TestNormalize_acceptsKoreanPlaceVariants(t *testing.T) {
	cases := []struct{ s, e string }{
		{"강남", "강남구청"},
		{"양재IC", "판교IC"},
		{"서울특별시 중구 세종대로 110", "인천국제공항 제1터미널"},
		{"광화문", "성수동"},
	}
	for _, c := range cases {
		if _, err := NormalizeInputs(c.s, c.e); err != nil {
			t.Errorf("rejected valid input %q→%q: %v", c.s, c.e, err)
		}
	}
}
