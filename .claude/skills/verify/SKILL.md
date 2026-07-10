---
name: verify
description: Drive the static dashboard (index.html) in headless Chromium and capture evidence.
---

# Verifying this repo's dashboard

`index.html` is the whole app — a static, dependency-free page (GitHub Pages).
No build step. It boots in **demo mode** (deterministic generated data) whenever
no ThingSpeak channel is configured, so it runs fully offline.

On boot it tries, in order: (1) a config saved in `localStorage` from a previous
edit/import/revert, (2) `fetch('home-dashboard-config.json')` — the repo's
committed config, (3) the built-in demo config. Opening the page via `file://`
(as below) makes step 2's `fetch` fail (Chromium blocks it under file:// —
CORS), so a plain `file://` launch always falls through to demo mode, same as
before this fetch step existed. To exercise the repo-config-loads-by-default
path, serve the directory over HTTP first (e.g. `python3 -m http.server` in
the repo root) and `goto` `http://localhost:PORT/index.html` instead — that
config has a real ThingSpeak channel ID, so expect a `.badge.err` for the
blocked network fetch in the sandbox, not a crash.

## Launch & drive

```bash
cd "$SCRATCHPAD" && npm i playwright-core --no-audit --no-fund
node - <<'EOF'
const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  p.on('pageerror', e => console.log('PAGEERROR', e.message));
  await p.goto('file:///home/user/home/index.html');
  await p.waitForTimeout(1200);           // boot renders after demo "fetch"
  // ...drive, screenshot, assert...
  await b.close();
})();
EOF
```

## Flows worth driving

- Dashboard: tiles (`.tile`), charts (`.chart-body svg`), demo badge (`.badge.demo`),
  range buttons (`.seg button`), per-card Table toggle (`.ghost:has-text("Table")`).
- Hover a chart → `#tip` tooltip becomes visible (crosshair readout).
- Tabs are hash-routed links in `nav.tabs`.
- Manage CRUD: modal form fields are `#modal input[name=…]` / `select[name=…]`,
  submit with `#modal button[type="submit"]`.
- Theme: `#theme-btn` cycles auto → light → dark (`documentElement.dataset.theme`).

## Gotchas

- Each Playwright launch gets a fresh profile — `localStorage` (all CRUD config)
  does **not** persist between launches; re-create state per run, or reload within one.
- Setting a bogus ThingSpeak channel exercises the error path: expect one blocked
  network request (`ERR_TUNNEL_CONNECTION_FAILED` in the sandbox) and a
  `.badge.err`, not a crash.
- Live ThingSpeak/Open-Meteo fetches are unreachable from the sandbox; demo mode
  is the verification surface.
