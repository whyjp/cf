package route

import "os"

// getenv is split out so the naver_test file can override it for the
// rare test that needs the binding without setting real environment
// variables. Production calls go straight through to os.Getenv.
func getenv(key string) string { return os.Getenv(key) }
