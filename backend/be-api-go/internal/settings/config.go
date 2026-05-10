package settings

import "github.com/kelseyhightower/envconfig"

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
}

// Load reads configuration from process environment variables.
func Load() (*Config, error) {
	var c Config
	if err := envconfig.Process("", &c); err != nil {
		return nil, err
	}
	return &c, nil
}
