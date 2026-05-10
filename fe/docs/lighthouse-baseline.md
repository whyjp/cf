# Lighthouse Baseline — Mobile (`/m.html`)

Captured during Sprint C6 (final SP-C polish). Run against the production
`vite build` output served via `vite preview` — i.e. the same bundles that
will ship behind the FastAPI mount.

## Method

```bash
cd fe
npm run build
npm run preview &           # serves http://localhost:4173/
CHROME_PATH=<chromium.exe> \
  npx lighthouse@11 http://localhost:4173/m.html \
  --emulated-form-factor=mobile \
  --output=json --output-path=./lh.json --quiet \
  --chrome-flags="--headless --no-sandbox --disable-gpu"
```

Local Chromium binary: Playwright's bundled `chromium-1217` (Windows
`chrome-win64/chrome.exe`). Lighthouse 11.7.1, HeadlessChrome/147.

## Baseline scores — 2026-05-10

| Category        | Score | Target | Status |
|-----------------|-------|--------|--------|
| Performance     | 77    | >= 80  | NEAR   |
| Accessibility   | 100   | >= 90  | PASS   |
| Best Practices  | 89    | >= 80  | PASS   |
| SEO             | 85    | >= 80  | PASS   |

### Performance metrics (mobile emulation, throttled)

| Metric                       | Value   |
|------------------------------|---------|
| First Contentful Paint       | 2.8 s   |
| Largest Contentful Paint     | 5.0 s   |
| Total Blocking Time          | 0 ms    |
| Cumulative Layout Shift      | 0.001   |
| Speed Index                  | 2.8 s   |

CLS and TBT are excellent. Performance score is held back by LCP/FCP —
both dominated by the Leaflet bundle + tile fetch on cold load. Code
splitting `useDetail`/Leaflet is already in place (`useDetail-*.js` chunk
ships separately), so the next move would be to defer Leaflet init until
after first paint, or self-host one tile + preload it.

## Targets going forward

- Performance >= 80 — within reach with one round of LCP work.
- Accessibility >= 90 — already at 100, lock in via lint rule.
- Best Practices and SEO already comfortably above bar.

## Notes

- Run on a dev machine with Playwright Chromium installed. CI does not
  yet run Lighthouse — wire up `lhci` in a follow-up sprint if the score
  needs to be enforced.
- Score variance run-to-run on the same machine: +/- 3 points. Treat
  Performance scores within that band as noise.
