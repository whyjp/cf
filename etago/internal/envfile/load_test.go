package envfile

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoad_setsKeysFromFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".env")
	body := "FOO=bar\n# comment\n\nBAZ=\"quoted value\"\nQUX='single'\nINVALIDLINE\n"
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}

	t.Setenv("FOO", "")
	t.Setenv("BAZ", "")
	t.Setenv("QUX", "")
	os.Unsetenv("FOO")
	os.Unsetenv("BAZ")
	os.Unsetenv("QUX")

	if err := Load(path); err != nil {
		t.Fatal(err)
	}
	if got := os.Getenv("FOO"); got != "bar" {
		t.Errorf("FOO: got %q want bar", got)
	}
	if got := os.Getenv("BAZ"); got != "quoted value" {
		t.Errorf("BAZ: got %q want 'quoted value'", got)
	}
	if got := os.Getenv("QUX"); got != "single" {
		t.Errorf("QUX: got %q want single", got)
	}
}

func TestLoad_doesNotOverridePreset(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".env")
	os.WriteFile(path, []byte("PRESET=fromfile\n"), 0o600)

	t.Setenv("PRESET", "fromenv")
	if err := Load(path); err != nil {
		t.Fatal(err)
	}
	if got := os.Getenv("PRESET"); got != "fromenv" {
		t.Errorf("preset overridden: got %q want fromenv", got)
	}
}

func TestLoad_missingFile_isSilent(t *testing.T) {
	if err := Load(filepath.Join(t.TempDir(), "no-such-env")); err != nil {
		t.Errorf("expected nil for missing file, got %v", err)
	}
}

func TestTrimQuotes(t *testing.T) {
	cases := map[string]string{
		`"hello"`:    "hello",
		`'hello'`:    "hello",
		`hello`:      "hello",
		`"unclosed`:  `"unclosed`,
		`'mixed"`:    `'mixed"`,
		``:           ``,
	}
	for in, want := range cases {
		if got := trimQuotes(in); got != want {
			t.Errorf("trimQuotes(%q): got %q want %q", in, got, want)
		}
	}
}

func TestLoadDefault_walksUp(t *testing.T) {
	root := t.TempDir()
	sub := filepath.Join(root, "a", "b", "c")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatal(err)
	}
	envPath := filepath.Join(root, ".env")
	if err := os.WriteFile(envPath, []byte("WALKUP_KEY=found\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	prev, _ := os.Getwd()
	os.Chdir(sub)
	defer os.Chdir(prev)

	os.Unsetenv("WALKUP_KEY")
	if err := LoadDefault(); err != nil {
		t.Fatal(err)
	}
	if got := os.Getenv("WALKUP_KEY"); got != "found" {
		t.Errorf("walk-up failed: got %q", got)
	}
}
