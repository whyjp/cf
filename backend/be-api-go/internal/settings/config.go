package settings

import (
	"os"

	"github.com/kelseyhightower/envconfig"
)

// osLookupEnv is a thin wrapper for os.Getenv to make the legacy fallback
// in Load() obviously a fallback (not part of the envconfig schema).
var osLookupEnv = os.Getenv

// Config is the runtime configuration for the be-api Go service.
//
// Defaults are tuned for the SP-D verification mode (D-1~D-7), which runs
// alongside the legacy Python be-api (port 8072). The Go service binds
// 8073 to allow side-by-side smoke and parity tests prior to D-8 cutover.
type Config struct {
	Host        string `envconfig:"BE_API_HOST" default:"127.0.0.1"`
	Port        int    `envconfig:"BE_API_PORT" default:"8073"`
	DatabaseURL string `envconfig:"DATABASE_URL" default:"postgresql://camfit:camfit@localhost:5432/camfit"`
	FalkorDBURL string `envconfig:"FALKORDB_URL" default:"redis://localhost:6379"`
	LogLevel    string `envconfig:"LOG_LEVEL" default:"info"`

	// D-3: ONNX semantic search assets. Empty paths disable the
	// /sites/search and /sites/{id}/similar endpoints — useful for the
	// D-1/D-2 integration tests which only need /healthz and /sites.
	OnnxLibPath       string `envconfig:"ONNXRUNTIME_LIB" default:""`
	OnnxModelPath     string `envconfig:"KO_SROBERTA_ONNX" default:""`
	OnnxTokenizerPath string `envconfig:"KO_SROBERTA_TOKENIZER" default:""`

	// D-5: ETA absorption (etago). Naver Cloud Platform Maps API keys
	// (Geocoding + Directions 5) and Kakao K1 / KakaoMobility key.
	// Both NCP keys empty → /eta falls back to the anonymous Naver search
	// path (captcha-prone) and Kakao K1 + OSRM. The endpoints stay live
	// either way; only the *quality* of the ETA changes.
	//
	// Aliases: NCP_CLIENT_ID / NCP_CLIENT_SECRET are read as fallbacks so
	// the same .env that fed the legacy etago CLI keeps working.
	NaverNCPClientID     string `envconfig:"NAVER_NCP_CLIENT_ID"`
	NaverNCPClientSecret string `envconfig:"NAVER_NCP_CLIENT_SECRET"`
	KakaoRESTKey         string `envconfig:"KAKAO_REST_KEY"`
}

// Load reads configuration from process environment variables.
//
// Compatibility: the legacy etago CLI read NCP_CLIENT_ID / NCP_CLIENT_SECRET
// (no NAVER_ prefix). For users with an existing .env, we honor those names
// as fallbacks when NAVER_NCP_CLIENT_ID / NAVER_NCP_CLIENT_SECRET are empty.
func Load() (*Config, error) {
	var c Config
	if err := envconfig.Process("", &c); err != nil {
		return nil, err
	}
	if c.NaverNCPClientID == "" {
		c.NaverNCPClientID = osLookupEnv("NCP_CLIENT_ID")
	}
	if c.NaverNCPClientSecret == "" {
		c.NaverNCPClientSecret = osLookupEnv("NCP_CLIENT_SECRET")
	}
	return &c, nil
}
