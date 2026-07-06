# 🏡 Home — sensors, dashboard & (eventually) automation

**Live dashboard: <https://cdomotor-g.github.io/home/>**

A zero-cost smart-home monitoring stack built around **LPUs — Local
Processing Units**: field devices that each carry a cluster of sensors and
push readings to **ThingSpeak** over plain HTTPS POST (no port forwarding, no
extra hardware). The first LPU is a Campbell Scientific **CR310** datalogger;
the architecture leaves room for more (ESP32, Arduino UNO, Raspberry Pi…),
each on its own ThingSpeak channel. A static dashboard on **GitHub Pages**
reads everything back, pulls **Open-Meteo** forecasts, and overlays
*prediction vs actual* on one chart. Collections, sensors, controls and
setpoints are all managed from a CRUD built into the dashboard.

> The dashboard boots in **demo mode** with generated data — including a
> simulated future ESP32 LPU running a mushroom house — until a ThingSpeak
> channel is configured in **Settings**, so you can explore everything right away.

## How it fits together

One LPU is live today; the same pattern repeats for every LPU that joins
(dashed = planned):

```mermaid
flowchart LR
    subgraph LPU1["LPU 1 — CR310 datalogger (live)"]
        S1[Tank levels ×2 · m] --> CR310
        S2[Tipping bucket · mm] --> CR310
        S3[Batt V · panel °C] --> CR310
        S4[Air T · RH · baro<br><i>coming soon</i>] --> CR310
    end
    subgraph LPU2["LPU 2 — ESP32 (planned)"]
        S5[Mushroom house<br>T · RH · CO₂] --> ESP32
    end
    subgraph LPUN["LPU n — Arduino UNO / Raspberry Pi (future)"]
        S6[Hydroponics · garden<br>pH · EC · soil moisture …] --> LPUn[Arduino / RPi]
    end
    CR310 -- "HTTPS POST every 5 min<br>(outbound only — no port forwarding)" --> TS[(ThingSpeak<br>one channel per LPU)]
    ESP32 -. "same pattern,<br>its own channel" .-> TS
    LPUn -.-> TS
    TS -- "read API (JSON, CORS)" --> DASH[Dashboard<br>GitHub Pages]
    OM[Open-Meteo<br>free forecast API] --> DASH
    TS -. "TalkBack queue per LPU (future):<br>each LPU polls for setpoint/valve commands" .-> CR310
    classDef future stroke-dasharray: 5 5;
    class LPU2,LPUN,ESP32,LPUn,S5,S6 future;
```

Everything is outbound from each LPU and browser-side in the dashboard —
there is no server to run, and every piece is free.

## LPUs — Local Processing Units

An LPU is any device in the field that can take measurements and make an
outbound HTTPS POST. Each LPU carries **multiple sensors** (and eventually
relays), owns **one ThingSpeak channel** (up to 8 fields), and runs its own
local logic so it keeps working when the internet doesn't.

| LPU | Status | Carries |
|---|---|---|
| **CR310 datalogger** | ✅ live | Tank levels ×2, rain gauge, battery & panel temp — air T / RH / baro soon |
| ESP32 | 🔜 planned | Mushroom house: temperature, humidity, CO₂ — plus heat-mat / humidifier relays |
| Arduino UNO (+ WiFi/Ethernet shield) | 💡 candidate | Hydroponics: pH, EC, water temperature, pump control |
| Raspberry Pi | 💡 candidate | Garden: soil-moisture array, camera, anything needing more compute |

Adding an LPU never touches the dashboard's code: create a new ThingSpeak
channel, point the device's firmware at it, then add its sensors in
**Manage** with the per-sensor *channel override* set to the new channel.

## Data storage: why ThingSpeak

| Option | Cost | Fit |
|---|---|---|
| **ThingSpeak** (recommended) | Free (non-commercial): ~3 M messages/yr, 4 channels, 8 fields each | One channel per LPU; CR310 `HTTPPost` works out of the box and every candidate LPU (ESP32 / Arduino / Pi) has an HTTPS client; browser-readable JSON API with CORS; **TalkBack** command queue gives a no-port-forwarding path to *controls* later |
| Google Sheets + Apps Script webhook | Free | Works, but Apps Script redirects trip up logger HTTP clients, and querying/aggregating from the browser is clunkier |
| InfluxDB Cloud free tier | Free | Nice queries, but **30-day retention** kills long-term tank/rain history |
| Commit CSVs to this repo via API | Free | Needs a GitHub token embedded in the logger program; API is awkward from CRBasic |

A 5-minute upload interval is ~105 k messages/year **per LPU** — about 3 % of
the free allowance each, so the four free channels comfortably host four LPUs
(mushrooms, hydroponics, garden…) on the same account.

### Channel field map — LPU 1 (CR310)

One channel per LPU, one field per measurement. The CR310's channel:

| Field | Measurement | Unit |
|---|---|---|
| 1 | Tank 1 level | m |
| 2 | Tank 2 level | m |
| 3 | Rain (total over upload interval) | mm |
| 4 | Logger battery | V |
| 5 | Panel temperature | °C |
| 6 | Air temperature *(soon)* | °C |
| 7 | Barometric pressure *(soon)* | hPa |
| 8 | Relative humidity *(soon)* | % |

The dashboard's default sensor config matches this map exactly — remap any of
it in **Manage** if you wire things differently. Each subsequent LPU gets its
own channel and field map (e.g. the planned ESP32: field 1 grow-room
temperature, field 2 humidity, field 3 CO₂).

## Getting live data flowing

1. **Create a ThingSpeak channel** (free account at thingspeak.com) with the
   8 fields above. Note the **Channel ID**, **Write API key** and (if you keep
   the channel private) the **Read API key**.
2. **Program the CR310** — adapt [`logger/CR310_ThingSpeak.CR300`](logger/CR310_ThingSpeak.CR300):
   drop in your Write key, keep your existing measurement code, and it posts
   every 5 minutes with `HTTPPost`. Rain is accumulated between posts so daily
   totals reconstruct exactly.
3. **Open the [dashboard](https://cdomotor-g.github.io/home/) → Settings** and
   enter the Channel ID + Read key, plus your latitude/longitude for forecasts.
4. Done — the demo badge disappears and you're looking at your own data.

**Adding another LPU** later is the same loop: create a channel for it, point
the device's HTTP client at ThingSpeak (`HTTPClient` on ESP32/Arduino, Python
`requests` on a Pi), and map its sensors in **Manage** using the per-sensor
channel override.

## The dashboard

- **Stat tiles** — latest reading per sensor with 24 h delta, a sparkline, and
  low/high alert thresholds (battery warns below 11.5 V out of the box).
- **Charts** — time-series per collection (sensors sharing a unit share an
  axis; nothing ever gets a second y-axis), rain as hourly/daily/weekly total
  bars, with crosshair tooltips, a table view on every chart, and
  24 h / 7 d / 30 d / 90 d ranges.
- **Forecast vs actual** — for any sensor mapped to an Open-Meteo variable
  (temperature, humidity, pressure, precipitation), measured data is drawn
  solid and the forecast dashed on the *same* chart, spanning the past 3 days
  and next 4, so you can see how the prediction tracked reality. Rain compares
  daily totals side-by-side.
- **Manage (CRUD)** — collections for areas/systems around the place (water,
  weather, mushroom house, hydroponics…), each holding **sensors** (name, unit,
  type, ThingSpeak field, alert range, forecast mapping, optional per-sensor
  channel override for sensors living on other LPUs) and **controls** (heater / cooler /
  fan / valve / humidifier / pump, linked sensor, auto/manual mode,
  **setpoint + deadband**, on-below or on-above behaviour).
- **Light & dark theme**, phone-friendly, no build step, no dependencies.

Dashboard configuration lives in the browser's localStorage; **Settings →
Export config** produces a JSON backup you can import on another device (or
commit here as your source of truth).

## Controls & automation roadmap

Controls created in the CRUD are configuration-first: the dashboard already
evaluates each one against live readings and shows what it *would* do
(ON / OFF / in deadband). Closing the loop, still with no port forwarding:

1. Wire relays/valves to the LPU (SW12 / control ports on the CR310; GPIO +
   relay boards on an ESP32 / Arduino / Pi).
2. Dashboard pushes setpoint changes and manual commands to that LPU's
   **ThingSpeak TalkBack** queue (a simple HTTPS POST from the browser).
3. Each LPU polls its TalkBack queue on a slow cycle (`HTTPGet` on the CR310),
   applies commands (open valve, new heater setpoint…), and reports state back
   on a status field.

Simple threshold automation (heater on below 18 °C ± 0.5) is best run *on the
LPU* so it keeps working when the internet doesn't; the dashboard is where
you edit the numbers.

## Repo contents

| Path | What |
|---|---|
| [`index.html`](index.html) | The whole dashboard — a single self-contained file served by GitHub Pages |
| [`logger/CR310_ThingSpeak.CR300`](logger/CR310_ThingSpeak.CR300) | LPU 1 firmware — CRBasic template: measurements + rain accumulation + `HTTPPost` to ThingSpeak |

Firmware for each future LPU (ESP32 sketch, Arduino sketch, Pi script…) lands
in [`logger/`](logger) alongside the CR310 program — one file per LPU.

*Dashboard URL note: served by GitHub Pages from the default branch — if Pages
is set to “Deploy from a branch”, it goes live once this lands on `main`.*
