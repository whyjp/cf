// Package envfile loads simple KEY=VALUE pairs from a .env file into the
// process environment. It is intentionally minimal — no third-party
// dependency, no variable expansion, no multiline values — just the
// 90% case for shipping a CLI that wants optional credentials.
package envfile

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Load reads path as a UTF-8 .env file and calls os.Setenv for each
// KEY=VALUE line that is not already set in the current environment.
// Comment lines (#) and blank lines are skipped. Surrounding single or
// double quotes around values are stripped. A missing file is not an
// error — Load returns nil so callers can treat .env as optional.
func Load(path string) error {
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	defer f.Close()

	s := bufio.NewScanner(f)
	for s.Scan() {
		line := strings.TrimSpace(s.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		eq := strings.IndexByte(line, '=')
		if eq <= 0 {
			continue
		}
		key := strings.TrimSpace(line[:eq])
		val := strings.TrimSpace(line[eq+1:])
		val = trimQuotes(val)
		if _, exists := os.LookupEnv(key); !exists {
			if err := os.Setenv(key, val); err != nil {
				return fmt.Errorf("setenv %s: %w", key, err)
			}
		}
	}
	return s.Err()
}

// LoadDefault searches for a .env file starting in the working
// directory and walking up to maxDepth parent directories. The first
// file found is loaded; missing files are silent. This handles the
// common case where the binary lives in a sub-directory of a project
// root that holds the .env catalog.
func LoadDefault() error {
	const maxDepth = 5
	cwd, err := os.Getwd()
	if err != nil {
		return err
	}
	dir := cwd
	for i := 0; i <= maxDepth; i++ {
		candidate := filepath.Join(dir, ".env")
		if _, err := os.Stat(candidate); err == nil {
			return Load(candidate)
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return nil
}

func trimQuotes(s string) string {
	if len(s) >= 2 {
		first, last := s[0], s[len(s)-1]
		if (first == '"' || first == '\'') && first == last {
			return s[1 : len(s)-1]
		}
	}
	return s
}
