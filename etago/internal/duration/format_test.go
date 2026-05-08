package duration

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/whyjp/etago/internal/parse"
	"github.com/whyjp/etago/internal/route"
)

func TestFormat_default_minutes(t *testing.T) {
	in, _ := parse.NormalizeInputs("강남역", "수원시청")
	got := Format(route.Duration{Min: 58, Source: "naver"}, in, Options{})
	if got != "58 min" {
		t.Errorf("got %q", got)
	}
}

func TestFormat_json_preservesUserText(t *testing.T) {
	in, _ := parse.NormalizeInputs("강남역", "수원시청")
	got := Format(route.Duration{Min: 58, Source: "naver"}, in, Options{JSON: true})
	if !strings.Contains(got, `"start":"강남역"`) {
		t.Errorf("user text not preserved: %s", got)
	}
	var env jsonEnvelope
	if err := json.Unmarshal([]byte(got), &env); err != nil {
		t.Fatal(err)
	}
	if env.DurationMin != 58 || env.Source != "naver" {
		t.Errorf("unexpected envelope: %+v", env)
	}
}

func TestFormat_json_zeroIsValid(t *testing.T) {
	in, _ := parse.NormalizeInputs("a", "b")
	got := Format(route.Duration{}, in, Options{JSON: true})
	var env jsonEnvelope
	if err := json.Unmarshal([]byte(got), &env); err != nil {
		t.Fatal(err)
	}
}
