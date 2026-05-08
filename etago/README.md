# etago

Drive ETA between two natural-language Korean place names — printed to STDOUT, no app login required (one-time NCP key registration).

```
$ etago "강남역" "수원시청"
33 min

$ etago --json "서울특별시 강남구 강남대로 396" "수원시청"
{"start":"서울특별시 강남구 강남대로 396","end":"수원시청","duration_min":33,"source":"naver"}
```

## Why

If all you need is the *single recommended drive time* between two Korean places, the official Korean map APIs ask for app keys, quotas, and billing. `etago` resolves the place name anonymously through Kakao Map's still-public search endpoint, then asks **Naver Map's Directions 5** API for the genuine traffic-aware ETA — the same number Naver's web UI shows. No login, no per-request token; one NCP API key registered once.

## Setup

### 1. Install

```bash
go install github.com/whyjp/etago/cmd/etago@latest
```

Or from source:

```bash
git clone https://github.com/whyjp/etago && cd etago
go build -o etago(.exe) ./cmd/etago
```

Requires Go 1.22+. Single self-contained binary.

### 2. Get NCP keys (free tier)

1. https://www.ncloud.com → 회원가입 + 결제수단 등록
2. https://console.ncloud.com → Services → AI·Application Service → **Maps** → 이용 신청
3. Maps → **Application** → 등록
   - Service: tick **Geocoding** + **Directions 5**
   - 서비스 환경: register your IP, or `0.0.0.0/0` for development
4. **인증 정보** → copy `Client ID` + `Client Secret`

Free tier: ~60 000 Directions calls / month, ~30 000 Geocoding / month.

### 3. Drop the keys into a `.env`

```env
# .env (sits next to the binary, or in a parent directory)
NCP_CLIENT_ID=your-client-id
NCP_CLIENT_SECRET=your-client-secret
```

`etago` walks up to five parent directories from the current working dir looking for `.env`. The repo's `.gitignore` already excludes it.

## Usage

```
etago [flags] <start> <end>

Flags:
  --json              emit JSON envelope instead of "<min> min"
  --timeout duration  total timeout (default 12s)
  --verbose           log per-source latency to stderr
  --ua string         User-Agent override
  --source string     auto | naver | kakao  (default auto)
```

Both `<start>` and `<end>` accept any Korean place text — station names, road-name addresses, jibun addresses, IC names. Bare lat/lng coordinates are rejected (use a place name).

### Exit codes

| code | meaning |
|------|---------|
| 0 | success |
| 1 | unknown / panic |
| 2 | input error (empty, coordinate, over-length) |
| 3 | external failure (every map source failed) |

## How it works

1. **Geocode** `<start>` and `<end>`:
   - Try **Naver NCP Geocoding v2** first (handles road-name and jibun addresses).
   - Fall back to **Kakao Map's anonymous K1 search** (`search.map.kakao.com`) for POIs / station names / landmarks that NCP geocoding can't resolve.
2. **Drive ETA** via **Naver NCP Directions 5** (`option=traoptimal`) — the same recommended-route engine the Naver web UI calls.
3. Round to the nearest minute, print, exit 0.
4. If NCP isn't configured (no `.env` or 401 from upstream), fall through to **Kakao K1 + OSRM** (`router.project-osrm.org`) — a fully anonymous backup. The `Source` field in JSON tells you which path won (`"naver"` vs `"kakao"`).

`--source naver` and `--source kakao` pin a single backend for tests; `auto` (default) prefers Naver when keys are present.

## Limitations

- **Driving only.** No transit, walking, cycling.
- **Single recommended route.** No alternatives, no toll-avoidance, no scheduled-departure forecasting.
- **Time only.** No coordinates, no polyline, no distance, no toll cost.
- **Korea only.** Both Naver and Kakao are domestic services.
- **No rate limiting.** If you call this in a tight loop you'll hit NCP quota or Kakao IP throttling. Sleep between calls.

## Windows

PowerShell + cmd default to cp949 for the console code page. If you see `?` characters in Korean output:

```powershell
chcp 65001
.\etago.exe "강남역" "수원시청"
```

## Tests

```bash
go test ./...                  # unit + mock (offline OK)
go test -tags=smoke ./tests/   # live network smoke (5 pairs)
```

The smoke test loads `.env` the same way the binary does, so it exercises the production chain end-to-end. It auto-skips when the host has no outbound network.

### Windows AppControl note

Some Windows installations block test binaries Go produces in `%TEMP%`. If `go test` reports an Application Control error, build the test binary into the project directory and run it directly:

```powershell
go test -c -o cmd-etago.test.exe .\cmd\etago
.\cmd-etago.test.exe -test.v
```

## License

MIT.
