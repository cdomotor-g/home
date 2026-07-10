#!/usr/bin/env python3
"""
LPU: Raspberry Pi + RTL-SDR -> 433 MHz weather station -> ThingSpeak.

Listens to a consumer weather station (e.g. the Digitech XC0434 outdoor
sensor array: temperature, humidity, wind speed/gust/direction, rain) with an
RTL-SDR Blog V3 dongle and rtl_433, aggregates readings, and POSTs one
ThingSpeak update per upload interval. Stdlib only — no pip installs.

Channel field map (matches the dashboard's "Backyard station" defaults):
  field1 = outdoor temperature (degC)      last reading in the interval
  field2 = outdoor humidity (%)            last reading
  field3 = wind speed, average (m/s)       mean over the interval
  field4 = wind gust (m/s)                 max over the interval
  field5 = wind direction (deg)            last reading
  field6 = rain over the interval (mm)     delta of the station's counter
  field7 = sensor battery OK (1/0)         last reading
  field8 = packets decoded this interval   a cheap RF-link health metric

Setup on the Pi:
  sudo apt install rtl-433          # or build from github.com/merbanan/rtl_433
  rtl_433 -f 433.92M -F json        # watch: note your station's "model" string
  # put that string in MODEL_FILTER below (or leave empty to take any station),
  # drop in your channel's Write API key, then:
  python3 rpi_rtl433_thingspeak.py

Run forever with systemd — /etc/systemd/system/rtl433-thingspeak.service:
  [Unit]
  Description=433MHz weather station -> ThingSpeak
  After=network-online.target
  [Service]
  ExecStart=/usr/bin/python3 /home/pi/home/logger/rpi_rtl433_thingspeak.py
  Restart=always
  RestartSec=30
  [Install]
  WantedBy=multi-user.target
then: sudo systemctl enable --now rtl433-thingspeak
"""

import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request

# ----------------------------------------------------------------- settings
WRITE_API_KEY = "VG88DX08VU00PM7B"   # this LPU's own channel
UPLOAD_INTERVAL_MIN = 10                        # ~105k msgs/yr at 5 min: well inside free tier
FREQUENCY = "917M"

# rtl_433 decodes dozens of protocols at once; filter to your station so a
# neighbour's sensor can't pollute the channel. Run `rtl_433 -F json` and copy
# the "model" value it prints for your station (and "id" after a battery swap
# re-pair, if you want to pin it). Empty filter = accept everything.
MODEL_FILTER = "Bresser-6in1"          # e.g. "Fineoffset-WHx080"
ID_FILTER = None           # e.g. 42 — or None to accept any id

RTL433_CMD = ["rtl_433", "-f", FREQUENCY, "-F", "json", "-M", "time:unix"]

# rtl_433 key -> ours (covers the common naming across station protocols)
KEYS_TEMP = ("temperature_C",)
KEYS_HUM = ("humidity",)
KEYS_WIND = ("wind_avg_m_s", "wind_speed_m_s", "wind_avg_km_h")
KEYS_GUST = ("wind_max_m_s", "gust_speed_m_s", "wind_max_km_h")
KEYS_DIR = ("wind_dir_deg",)
KEYS_RAIN = ("rain_mm",)   # cumulative counter on most stations
KEYS_BATT = ("battery_ok",)


def pick(record, keys):
    for k in keys:
        if k in record and record[k] is not None:
            v = float(record[k])
            if k.endswith("km_h"):
                v /= 3.6
            return v
    return None


class Interval:
    """Aggregates decoded packets between ThingSpeak posts."""

    def __init__(self):
        self.last = {}          # field -> last value
        self.wind_sum = 0.0
        self.wind_n = 0
        self.gust_max = None
        self.packets = 0

    def add(self, rec):
        self.packets += 1
        for name, keys in (("temp", KEYS_TEMP), ("hum", KEYS_HUM),
                           ("dir", KEYS_DIR), ("batt", KEYS_BATT)):
            v = pick(rec, keys)
            if v is not None:
                self.last[name] = v
        w = pick(rec, KEYS_WIND)
        if w is not None:
            self.wind_sum += w
            self.wind_n += 1
        g = pick(rec, KEYS_GUST)
        if g is not None:
            self.gust_max = g if self.gust_max is None else max(self.gust_max, g)
        r = pick(rec, KEYS_RAIN)
        if r is not None:
            self.last["rain_counter"] = r


def post(fields):
    data = {"api_key": WRITE_API_KEY}
    data.update({k: v for k, v in fields.items() if v is not None})
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request("https://api.thingspeak.com/update", data=body)
    with urllib.request.urlopen(req, timeout=30) as res:
        entry = res.read().decode().strip()
    if entry == "0":
        raise RuntimeError("ThingSpeak rejected the update (rate limit or bad key)")
    return entry


def main():
    if WRITE_API_KEY.startswith("YOUR_"):
        sys.exit("Edit WRITE_API_KEY first (this LPU's own ThingSpeak channel).")
    proc = subprocess.Popen(RTL433_CMD, stdout=subprocess.PIPE, text=True)
    print(f"listening via: {' '.join(RTL433_CMD)}", flush=True)

    agg = Interval()
    prev_rain = None
    next_post = time.time() + UPLOAD_INTERVAL_MIN * 60

    for line in proc.stdout:
        line = line.strip()
        if line.startswith("{"):
            try:
                rec = json.loads(line)
            except ValueError:
                rec = None
            if rec is not None:
                matches_model = not MODEL_FILTER or rec.get("model") == MODEL_FILTER
                matches_id = ID_FILTER is None or rec.get("id") == ID_FILTER
                if matches_model and matches_id:
                    agg.add(rec)
                    print(f"packet #{agg.packets}: model={rec.get('model')} id={rec.get('id')}", flush=True)

        # Checked on every line (not just matching packets) so a filter
        # mismatch or a quiet station can't stall the upload schedule.
        if time.time() < next_post:
            continue
        next_post += UPLOAD_INTERVAL_MIN * 60

        # rain: the station reports a lifetime counter — post the interval delta
        rain_mm = None
        counter = agg.last.get("rain_counter")
        if counter is not None:
            if prev_rain is not None and counter >= prev_rain:
                rain_mm = round(counter - prev_rain, 2)
            prev_rain = counter

        fields = {
            "field1": agg.last.get("temp"),
            "field2": agg.last.get("hum"),
            "field3": round(agg.wind_sum / agg.wind_n, 2) if agg.wind_n else None,
            "field4": agg.gust_max,
            "field5": agg.last.get("dir"),
            "field6": rain_mm,
            "field7": agg.last.get("batt"),
            "field8": agg.packets,
        }
        try:
            entry = post(fields)
            print(f"posted entry {entry}: {fields}", flush=True)
        except Exception as e:  # keep listening; the next interval retries
            print(f"post failed: {e}", file=sys.stderr, flush=True)
        agg = Interval()

    sys.exit(f"rtl_433 exited with code {proc.wait()}")


if __name__ == "__main__":
    main()
