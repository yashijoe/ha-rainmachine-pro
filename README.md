# RainMachine Pro for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=yashijoe&repository=ha-rainmachine-pro&category=integration)

A custom Home Assistant integration for **RainMachine** smart irrigation controllers. Connects directly to your RainMachine via its local API — no cloud required.

## Features

- **Local polling** — communicates directly with your RainMachine on your LAN
- **Today's watering summary** — total irrigation duration (including manual/forced runs) with statistics support for long-term tracking
- **Per-zone details** — scheduled vs actual duration, start time, and skip reason for each zone
- **Planned zone durations** — each program switch exposes expected watering duration per active zone (suggested, custom, or not set); each zone sensor exposes expected duration per program
- **Per-zone duration type control** — select `suggested`, `custom`, or `not set` per zone per program; set custom duration (minutes) and WaterSense percentage independently
- **Program duration adjustment** — per-program +/− buttons adjust all active zone durations by a fixed 5% of each zone's WaterSense reference time; works for both suggested and custom zones
- **Run countdown** — per-zone and per-program sensors showing remaining time as `M:SS` during active watering; works for both scheduled and manual runs
- **Pause watering** — pause all active watering for a configurable duration (1–720 minutes) with a live countdown sensor; cancellable by setting duration to 0
- **Cycle & Soak** — per-program cycle & soak control: off, auto (device decides), or custom (2–50 cycles, 0–300 min soak)
- **Irrigation forecast** — 8 sensors per enabled program: yesterday's actual irrigation and a 7-day forecast (days 0–6), each with scheduled and computed seconds per zone
- **Per-zone manual irrigation** — per-zone configurable duration (0.5–300 min) and a start button to immediately run that zone for the set duration
- **Per-zone stop/cancel** — per-zone button to stop a running zone or cancel a queued zone in a program without affecting other zones
- **ET coefficient** — per-zone ET coefficient (0.01–2.0) exposed as a zone switch attribute (updated every 5 min) and as an optional config number entity with a dedicated apply button
- **Editable program start time** — set each program's scheduled start time directly from Home Assistant
- **Sun-based start times** — start (or finish) each program a configurable number of minutes before/after sunrise or sunset, matching the device's start time modes
- **Editable program frequency** — set each program's irrigation schedule (Daily, Every N days, Odd/Even days, or specific weekdays) directly from Home Assistant
- **Shift program next run** — action to move a program's next scheduled run earlier or later by whole days (re-phases Every-N-days cycles)
- **Weather adaptive watering** — per-program switch to enable/disable the use of internet weather data for adaptive watering
- **Adaptive frequency** — per-program switch to enable/disable adaptive watering frequency adjustment
- **Zone and program control** — start/stop irrigation zones and programs, enable/disable them
- **Rain delay control** — view current delay status and set new delays directly from Home Assistant
- **Freeze protection** — enable/disable and set the freeze protection temperature threshold
- **Restriction monitoring** — binary sensors for all active watering restrictions
- **Weather parser status** — last run timestamp for each configured weather source
- **7-day forecast** — daily weather condition, temperature, rain, and evapotranspiration
- **Firmware update** — trigger firmware updates from the Home Assistant update panel
- **Reboot button** — reboot the controller directly from Home Assistant
- **Fully configurable from UI** — no YAML needed
- **Multi-language** — English, Italian, French, German, and Spanish translations included

## Requirements

- Home Assistant 2024.1.0 or newer
- A RainMachine controller accessible on your local network
- The RainMachine API must be reachable via HTTPS (default port 8080)

## Installation

### HACS (recommended)

1. Click the button above, or open HACS in Home Assistant and search for **RainMachine Pro**
2. Install the integration
3. Restart Home Assistant

### Manual

1. Download the latest release from GitHub
2. Extract the `custom_components/rainmachine_pro` folder into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **RainMachine Pro**
3. Enter the following:
   - **Host**: IP address of your RainMachine (e.g., `192.168.50.2`)
   - **Port**: API port (default: `8080`)
   - **Password**: your RainMachine password
   - **Update interval**: slow polling frequency in minutes (default: `5`, range: 1–60) — weather, forecast, restrictions, firmware
   - **Zone/program update interval**: fast polling frequency in seconds (default: `10`, range: 5–60) — zone and program run state
   - **Timeout**: connection timeout in seconds (default: `20`, range: 5–120)
4. Click **Submit**
5. **Zone configuration** — enable/disable each zone and customize display names; only enabled zones create entities. If your controller has a master valve, it will appear here with its name from the RainMachine app (e.g. "Master Valve") and can be enabled/disabled independently.
6. **Program configuration** — enable/disable each program and customize display names; only enabled programs create entities
7. **Parser configuration** — select which weather parsers generate sensor entities

### Options (post-setup)

Go to **Settings** → **Devices & Services** → **RainMachine Pro** → **Configure** to change update intervals, timeout, zone/program names, and parser configuration.

## Entities

### Sensors

| Entity | Description | Unit | State Class |
|--------|-------------|------|-------------|
| `sensor.rainmachine_today_watering` | Total actual irrigation time today (including manual runs) | min | `total` |
| `sensor.rainmachine_today_watering_scheduled` | Total scheduled irrigation time today | min | `total` |
| `sensor.rainmachine_rain_delay` | Current rain delay status | — | — |
| `sensor.rainmachine_zone_<n>` | Per-zone watering details | min | `measurement` |
| `sensor.rainmachine_parser_*` | Last run time for each weather parser | — | `timestamp` |
| `sensor.rainmachine_forecast_<n>` | Daily forecast (yesterday through +5 days) | — | — |
| `sensor.<zone>_run_countdown` | Remaining time for currently running zone (`M:SS`); `null` when idle | — | — |
| `sensor.<program>_run_countdown` | Remaining time for currently running program (`M:SS`); `null` when idle | — | — |
| `sensor.rainmachine_pause_countdown` | Live countdown of remaining pause time as `M:SS`; `null` when not paused or when a zone starts running | — | — |
| `sensor.rainmachine_flow_sensor_consumed_liters` | Total water consumed by the flow meter (for the Energy/water dashboard); `device_class: water`, `state_class: total_increasing`. **Disabled by default** — enable when a flow meter is installed | L | `total_increasing` |
| `sensor.rainmachine_<program>_irrigation_forecast_y` | Yesterday's actual irrigation for the program (total `userDuration` in seconds) | — | — |
| `sensor.rainmachine_<program>_irrigation_forecast_0` … `_6` | 7-day irrigation forecast for the program (day 0 = today … day 6); state = total `scheduledWateringTime` in seconds | — | — |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.rainmachine_watering_active` | ON while any zone is watering — manual, program or single-zone run (`device_class: running`; attributes: active zones, program, remaining seconds). Updates on the fast poll interval. **Disabled by default** |
| `binary_sensor.rainmachine_freeze_restriction` | Active freeze restriction |
| `binary_sensor.rainmachine_hourly_restriction` | Active hourly restriction |
| `binary_sensor.rainmachine_month_restriction` | Active month restriction |
| `binary_sensor.rainmachine_rain_delay_restriction` | Active rain delay restriction |
| `binary_sensor.rainmachine_weekday_restriction` | Active weekday restriction |
| `binary_sensor.rainmachine_rain_sensor` | Rain sensor triggered (disabled by default) |
| `binary_sensor.rainmachine_flow_sensor` | Flow sensor active (disabled by default) |

### Switches

| Entity | Description |
|--------|-------------|
| `switch.<zone_name>` | Start/stop a zone manually (10 min default) — attributes: `uid`, `zid`, `et_coefficient`, `running`, `remaining`, `machine_duration`, `flag`, `last_run_start`, `last_run_end`, `next_run` |
| `switch.<zone_name>_enabled` | Enable/disable a zone |
| `switch.<program_name>` | Start/stop a program — see attributes below |
| `switch.<program_name>_enabled` | Enable/disable a program |
| `switch.<program_name>_frequency_Mon` … `switch.<program_name>_frequency_Sun` | Weekday toggles for "Selected days" frequency (7 switches per program, config category) |
| `switch.<program_name>_weather_adaptive_watering` | Enable/disable weather-adaptive watering per program (ON = uses internet weather data, OFF = ignores internet weather) |
| `switch.<program_name>_use_adaptive_frequency` | Enable/disable adaptive watering frequency per program (ON = 50% adaptive adjustment, OFF = 0%) |
| `switch.rainmachine_freeze_protection` | Enable/disable freeze protection |
| `switch.rainmachine_extra_water_on_hot_days` | Enable/disable extra watering on hot days |
| `switch.rainmachine_rain_sensor` | Enable/disable the hardware rain sensor (`provision/useRainSensor`); **disabled by default** in entity registry — enable manually to use |

### Number

| Entity | Description | Range |
|--------|-------------|-------|
| `number.rainmachine_rain_delay_days` | Set rain delay | 0–14 days |
| `number.<program_name>_frequency_interval` | Days between runs when frequency is "Every N days" | 1–14 days |
| `number.<program>_<zone>_custom_duration` | Custom duration for a zone in a program (config category) | 0.5–299.5 min, step 0.5 |
| `number.<program>_<zone>_watering_percentage` | WaterSense `userPercentage` for a zone in a program (config category) | 10–200%, step 5% |
| `number.rainmachine_pause_duration` | Pause duration in minutes; set to 0 to cancel an active pause | 0–720 min, step 1 |
| `number.<zone>_manual_duration` | Duration for the next manual zone run | 0.5–300 min, step 0.5, default 10 min |
| `number.<zone>_et_coefficient` | Zone ET coefficient — WaterSense evapotranspiration adjustment factor; reads from device every 5 min, stores pending value until applied via the apply button (disabled by default, config category) | 0.01–2.0, step 0.01 |
| `number.<program>_cycle_soak_cycles` | Number of cycles for Cycle & Soak (custom mode; pending when not in custom mode) | 2–50, step 1 |
| `number.<program>_cycle_soak_min` | Soak time between cycles (custom mode; pending when not in custom mode) | 0–300 min, step 1 |
| `number.<program>_sun_offset` | Minutes before/after sunrise/sunset for sun-based start time modes (pending when mode is *Time of day*, config category) | 0–720 min, step 1 |

### Button

| Entity | Description |
|--------|-------------|
| `button.rainmachine_reboot` | Reboot the RainMachine controller |
| `button.<program_name>_increase_duration` | Increase all active zone durations by 5% of each zone's WaterSense reference time |
| `button.<program_name>_decrease_duration` | Decrease all active zone durations by 5% of each zone's WaterSense reference time |
| `button.rainmachine_pause_watering` | Send a pause command using the duration configured in `number.rainmachine_pause_duration` |
| `button.<zone>_start_manual` | Start the zone for the duration set in `number.<zone>_manual_duration`; triggers a zone run countdown |
| `button.<zone>_stop_zone` | Stop a running zone or cancel a queued zone in a program without affecting other zones (disabled by default) |
| `button.<zone>_apply_et_coefficient` | Write the pending ET coefficient value to the device and refresh zone properties (disabled by default, config category) |

### Select

| Entity | Description | Options |
|--------|-------------|--------|
| `select.rainmachine_freeze_protection_temperature` | Freeze protection threshold | −7 °C to +4 °C |
| `select.<program_name>_frequency` | Irrigation frequency type | Daily / Every N days / Odd days / Even days / Selected days |
| `select.<program>_<zone>_duration_type` | Duration type for a zone in a program (config category) | `suggested` / `custom` / `not set` |
| `select.<program>_cycle_soak_mode` | Cycle & Soak mode for the program (config category) | `off` / `auto` / `custom` |
| `select.<program>_start_time_mode` | Start time mode for the program (config category) | `time of day` / `before/after sunrise` / `before/after sunset` / `finish before/after sunrise` / `finish before/after sunset` |

### Time

| Entity | Description |
|--------|-------------|
| `time.<program_name>_start_time` | Scheduled start time for the program (editable). In sun-based modes it shows the device-computed start time; setting it switches the program back to *Time of day* mode |

### Update

| Entity | Description |
|--------|-------------|
| `update.rainmachine_firmware` | Firmware update status and trigger |

### Sensor Attributes

**Zone switches** include:

- `uid` — hardware zone ID (always available)
- `zid` — same as `uid`; the field name used in the watering queue API (always available)
- `et_coefficient` — zone ET coefficient (evapotranspiration adjustment factor, 0.01–2.0); read from device every 5 min via slow coordinator; `null` if not available
- `running` — current queue status: localized string (`"In irrigazione"` / `"Watering"` when active, `"In attesa"` / `"Queued"` when waiting in queue); `null` when zone is not in queue
- `remaining` — seconds remaining for this zone's current run; `null` when not in queue. Updated every 10 seconds.
- `machine_duration` — duration in seconds computed by RainMachine for this run (weather-adjusted); `null` when not in queue. Varies per zone and per program.
- `flag` — localized reason string for the current watering state (e.g. `"Irrigazione normale"` / `"Normal watering"`, `"Interrotto dal sensore pioggia"` / `"Stopped by rain sensor"`); `null` when not in queue
- `last_run_start` / `last_run_end` — start and end timestamps of the previous run
- `next_run` — next scheduled run timestamp

**Zone sensors** include:

- `userDuration` / `userDuration_display` — scheduled duration
- `realDuration` / `realDuration_display` — actual duration
- `startTime` — scheduled start time
- `flag` — reason if watering was skipped
- `<program name>` — planned duration in seconds for each program that includes this zone
- `<program name>_type` — `suggested` (WaterSense adaptive), `custom` (user-set fixed duration), or `not set` (zone not active in this program); translated per HA language

**Program switches** include:

- `enabled` — `on` or `off` (program active state)
- `next_run` / `last_run` — next and last run timestamps
- `start_time` — scheduled start time (HH:MM); computed by the device in sun-based modes
- `start_time_mode` — start time mode key (`time_of_day`, `before_sunrise`, `after_sunrise`, `before_sunset`, `after_sunset`, `finish_before_sunrise`, `finish_after_sunrise`, `finish_before_sunset`, `finish_after_sunset`)
- `sun_offset_minutes` — minutes before/after sunrise/sunset (only present in sun-based modes)
- `frequency` — translated frequency label (e.g. "Daily", "Ogni giorno")
- `<zone name>` — planned duration in seconds for each HA-enabled zone (0 if not active in this program)
- `<zone name>_type` — `suggested` (WaterSense adaptive), `custom` (user-set fixed duration), or `not set` (zone not active in this program); translated per HA language
- `total_duration` — total planned seconds across all active zones

**Run countdown sensors** include:

- `remaining_seconds` — remaining seconds as integer (useful for automations)
- `last_run_start` / `last_run_end` — start and end time of the previous run (zone sensors only)

**Forecast sensors** include:

- `temperature` / `min_temperature` / `max_temperature`
- `rain` / `precipitation_forecast` — actual and forecast rainfall in mm
- `EvapoTranspiration` — ET0 value in mm
- `hail_probability` — maximum hourly hail probability for the day (0–100 %), sourced from iLMeteo parser hourly data via `/api/4/parser/{id}/data/`; falls back to 0 if parser not installed
- `meteocode` / `state_translated`

**Rain delay sensor** includes:

- `days_remaining` / `hours_remaining` / `minutes_remaining` / `seconds_remaining`
- `ends_at`

**Irrigation forecast sensors** include (per zone, localized attribute names):

- `scheduled_sec` — total scheduled seconds for the program on that day
- `computed_sec` — total computed seconds for the program on that day
- `<zone>_scheduled_sec` — scheduled seconds for that zone
- `<zone>_computed_sec` — computed seconds for that zone
- `<zone>_watering_flag` — watering flag for that zone (localized)

## Run Countdown

Each HA-enabled zone and each enabled program exposes a countdown sensor (diagnostic category, enabled by default):

- **`sensor.<zone>_run_countdown`** — remaining time for the currently running zone as `M:SS` (e.g. `5:30`). Returns `null` when the zone is not running.
- **`sensor.<program>_run_countdown`** — same for the whole program.

The value comes directly from the device's `remaining` field in the watering queue, which already accounts for weather-adaptive adjustments. The sensor updates every 10 seconds (fast coordinator). It works for both scheduled and manual starts — when started from HA via the zone switch, the coordinator refreshes immediately so the countdown appears within 1–2 seconds.

The `remaining_seconds` attribute is also available for use in automations.

## Pause Watering

Three entities work together to pause and monitor all active irrigation:

- **`number.rainmachine_pause_duration`** — set the desired pause duration in minutes (1–720). Setting the value to `0` cancels any active pause.
- **`button.rainmachine_pause_watering`** — sends the pause command to the controller using the duration currently set in `number.rainmachine_pause_duration`.
- **`sensor.rainmachine_pause_countdown`** — displays the remaining pause time as `M:SS` (e.g. `4:32`). Returns `null` when no pause is active. The sensor clears automatically as soon as a zone starts running.

**Typical usage:**
1. Set `number.rainmachine_pause_duration` to the desired number of minutes (e.g. `30`).
2. Press `button.rainmachine_pause_watering`.
3. Monitor `sensor.rainmachine_pause_countdown` to track remaining pause time.
4. To cancel early, set `number.rainmachine_pause_duration` to `0` and press the button again, or simply start a zone/program.

## Stop / Cancel a Queued Zone

When a program is running, zones that have not yet started are queued on the device. The `button.<zone>_stop_zone` entity (disabled by default) lets you cancel a specific queued zone without stopping the entire program or waiting for its turn.

- **`button.<zone>_stop_zone`** — sends `POST /api/4/zone/{uid}/stop` to the device. Works whether the zone is currently running or queued. The fast coordinator refreshes immediately so the queue state updates within 1–2 seconds.

**Typical usage:**
1. Enable `button.<zone>_stop_zone` for the desired zone(s) in **Settings** → **Devices & Services** → **RainMachine Pro** → entity list.
2. While a program is running, press the button for any zone you want to cancel before it starts.
3. The zone is removed from the queue; the program continues with the remaining zones unaffected.

## ET Coefficient

The ET coefficient (`ETcoef`) is a per-zone WaterSense adjustment factor (range 0.01–2.0) that scales the reference evapotranspiration used to compute automatic irrigation durations.

Three ways to interact with it:

- **`switch.<zone>` attribute `et_coefficient`** — always available on every zone run switch; read from the device every 5 minutes via the slow coordinator. Use this for read-only monitoring and automations.
- **`number.<zone>_et_coefficient`** — optional config entity (disabled by default). Reads the current value from the device every 5 minutes. When you change the value in HA, it is stored as a pending value and does **not** immediately write to the device; the displayed value reflects your pending change until the button is pressed or HA is restarted.
- **`button.<zone>_apply_et_coefficient`** — optional config entity (disabled by default). Press to write the pending ET coefficient value to the device (`POST /api/4/zone/{uid}/properties`), clear the pending value, and trigger an immediate slow coordinator refresh. If no pending value exists, the current device value is re-sent.

**Typical usage:**
1. Enable `number.<zone>_et_coefficient` and `button.<zone>_apply_et_coefficient` for the desired zone in **Settings** → **Devices & Services** → **RainMachine Pro** → entity list.
2. Set `number.<zone>_et_coefficient` to the desired value (e.g. `1.2`).
3. Press `button.<zone>_apply_et_coefficient`.
4. After ~5 seconds the slow coordinator refreshes and `switch.<zone>` attribute `et_coefficient` reflects the new value.

## Cycle & Soak

For each enabled program, three CONFIG-category entities control the cycle & soak behaviour:

- **`select.<program>_cycle_soak_mode`** — selects the mode:
  - `off` — cycle & soak disabled (`cs_on = false`)
  - `auto` — device computes cycles automatically (`cs_on = true, cycles = -1`)
  - `custom` — user-defined cycles and soak time (`cs_on = true, cycles = N, soak = S`)

- **`number.<program>_cycle_soak_cycles`** — number of cycles (2–50, step 1). Applies immediately when mode is already `custom`; stored as a pending value otherwise and applied the next time `custom` is selected.

- **`number.<program>_cycle_soak_min`** — soak duration in minutes (0–300, step 1). Same apply/pending logic as cycles.

**Typical usage:**
1. Set `number.<program>_cycle_soak_cycles` to the desired cycle count (e.g. `3`).
2. Set `number.<program>_cycle_soak_min` to the desired soak time in minutes (e.g. `10`).
3. Select `custom` in `select.<program>_cycle_soak_mode` — both values are sent to the controller in one call.

To switch to automatic mode, select `auto`. To disable cycle & soak entirely, select `off`.

The program switch's per-zone duration attributes and `total_duration` report each zone's **total watering time for the next run**, matching the controller's "total watering time" figure. For zones with a suggested (weather-adaptive) duration this includes the program's frequency multiplier — e.g. an every-2-days program waters 2× the daily reference per run. Cycle & soak splits this total into cycles with soak rest in between; it does not change the total.

## Irrigation Forecast

For each enabled program, 8 sensors expose irrigation forecast data — one for yesterday's actual run and one for each of the next 7 days:

- **`sensor.rainmachine_<program>_irrigation_forecast_y`** — yesterday's actual irrigation. State = total scheduled seconds (`userDuration`). Source: `/api/4/watering/log/details`.
- **`sensor.rainmachine_<program>_irrigation_forecast_0`** … **`_6`** — 7-day irrigation forecast (day 0 = today, day 6 = six days from now). State = total `scheduledWateringTime` in seconds. Source: `/api/4/dailystats/details`.

All 8 sensors share the same attribute structure, with values per zone (localized attribute names):

| Attribute | Description |
|-----------|-------------|
| `scheduled_sec` | Total scheduled seconds for the program on that day |
| `computed_sec` | Total computed (weather-adjusted) seconds for the program on that day |
| `<zone>_scheduled_sec` | Scheduled seconds for that specific zone |
| `<zone>_computed_sec` | Computed seconds for that specific zone |
| `<zone>_watering_flag` | Watering flag for that zone (localized) |

These sensors are updated by the slow coordinator (default every 5 minutes).

## Per-Zone Manual Irrigation

For each HA-enabled zone, two entities allow starting a manual run with a configurable duration:

- **`number.<zone>_manual_duration`** — desired run duration in minutes (0.5–300, step 0.5, default 10). This is independent of the zone switch default.
- **`button.<zone>_start_manual`** — immediately starts the zone for the duration configured in `number.<zone>_manual_duration`. The zone run countdown sensor (`sensor.<zone>_run_countdown`) activates within 1–2 seconds.

**Typical usage:**
1. Set `number.<zone>_manual_duration` to the desired number of minutes (e.g. `5`).
2. Press `button.<zone>_start_manual`.
3. Monitor `sensor.<zone>_run_countdown` to track the remaining time.

## Per-Zone Duration Type

For each HA-enabled zone in each enabled program, three CONFIG-category entities are available:

**`select.<program>_<zone>_duration_type`** — switches between three modes (translated in all 5 languages):
- `suggested` — sets `active=true, duration=0`; device computes duration from WaterSense `referenceTime × userPercentage`
- `custom` — sets `active=true` with an explicit duration; if the current device duration is 0, falls back to `referenceTime` or 600 s
- `not set` — sets `active=false` (zone excluded from this program)

**`number.<program>_<zone>_custom_duration`** — desired custom duration in minutes (0.5–299.5, step 0.5, box input). Independent of the current mode — value is preserved via `RestoreEntity` even when the zone is in suggested or not set mode. Syncs from device only when in custom mode.

**`number.<program>_<zone>_watering_percentage`** — WaterSense `userPercentage` (10–200%, step 5%). Directly writes to the device and affects the suggested duration calculation.

## Program Duration Adjustment

Each enabled program exposes two button entities:

- **`button.<program>_increase_duration`** — adds 5% of each zone's WaterSense `referenceTime` to its current duration
- **`button.<program>_decrease_duration`** — subtracts 5% of each zone's WaterSense `referenceTime` from its current duration

The step is fixed at **5% of `referenceTime`** (the WaterSense 100% reference for each zone), which matches the RainMachine app's +/− behaviour. The resulting `userPercentage` is clamped to the range 5%–200%.

For **custom zones** (`duration > 0`): `current_pct` is derived from `duration / referenceTime`; both `userPercentage` and `duration` are updated (`duration = round(referenceTime × new_pct)`).
For **suggested zones** (`duration == 0`): only `userPercentage` is updated; the device recomputes the actual duration automatically.
Zones without a valid `referenceTime` are skipped. `not set` zones (`active=false`) are skipped.

## Program Frequency Editing

Each enabled program exposes three types of entities for schedule editing (all `EntityCategory.CONFIG`, hidden from the main dashboard by default):

1. **`select.<program>_frequency`** — choose the frequency type:
   - `Daily` — runs every day
   - `Every N days` — runs every N days (set N via the interval number entity)
   - `Odd days` — runs on odd-numbered calendar days
   - `Even days` — runs on even-numbered calendar days
   - `Selected days` — runs on specific weekdays (toggle each day individually)

2. **`number.<program>_frequency_interval`** — the interval N (1–14 days) used when type is *Every N days*. Changing this value immediately updates the device if the program is already set to *Every N days*; otherwise the value is stored and applied next time you switch to that type.

3. **`switch.<program>_frequency_Mon` … `switch.<program>_frequency_Sun`** — one toggle per weekday. Toggling a day immediately updates the device if the program is already set to *Selected days*; otherwise the state is stored as a pending value.

Only one frequency type is active at a time. Switching type via the select entity preserves previously configured parameters where possible (e.g. switching back to *Every N days* restores the last used interval).

## Sun-Based Start Times

Each enabled program exposes two entities for start time mode editing (both `EntityCategory.CONFIG`), mirroring the START TIME section of the device web UI:

1. **`select.<program>_start_time_mode`** — choose how the start time is determined:
   - *Time of day* — fixed HH:MM start (set via `time.<program>_start_time`)
   - *Before/After sunrise*, *Before/After sunset* — the program **starts** N minutes relative to the sun event
   - *Finish before/after sunrise*, *Finish before/after sunset* — the program **finishes** N minutes relative to the sun event (the device derives the start time from the program's total duration; depending on duration, the start may be limited to midnight)

2. **`number.<program>_sun_offset`** — the offset N (0–720 minutes). Changing it immediately updates the device if the program is already in a sun-based mode; otherwise the value is stored as pending and applied next time a sun-based mode is selected.

In sun-based modes the device recomputes the effective start time daily from its location's sunrise/sunset; `time.<program>_start_time` reflects the computed value. Setting the time entity to an explicit HH:MM switches the program back to *Time of day* mode, matching the radio-button coupling in the device UI. Switching between sun-based modes (e.g. *Before sunrise* → *After sunset*) preserves the current offset minutes.

## Shift Program Next Run

The `rainmachine_pro.shift_program_next_run` action moves a program's next scheduled run earlier or later by whole days, targeting the program's run switch:

```yaml
action: rainmachine_pro.shift_program_next_run
target:
  entity_id: switch.rainmachine_main_garden
data:
  days: 1   # positive = later, negative = earlier (−31 to 31)
```

It works by re-anchoring the program's `startDate` to the device's current `nextRun` plus `days`, which re-phases the watering cycle — the same mechanism as the "next run" date picker in the RainMachine app.

- Meaningful for **Every N days** programs, where the start-date anchor sets the phase of the cycle. Daily programs always run today/tomorrow regardless of anchor; weekday/odd-even schedules are not affected by a one-day nudge.
- The device won't schedule a run in the past: shifting backward onto a time slot that has already elapsed today rolls forward to the next cycle instead.
- The program must currently have a next run (enabled and schedulable); otherwise the call fails.
- The shift is computed from a fresh read of the device's `nextRun`, so repeated calls accumulate correctly.

## Weather Adaptive Watering

Each enabled program exposes a `switch.<program>_weather_adaptive_watering` entity (config category):

- **ON** — the program uses internet weather data to adjust watering (sets `ignoreInternetWeather = false`)
- **OFF** — the program ignores internet weather and waters with fixed durations (sets `ignoreInternetWeather = true`)

This maps directly to the "ignore Internet Weather" checkbox in the RainMachine app.

## Adaptive Frequency

Each enabled program exposes a `switch.<program>_use_adaptive_frequency` entity (config category):

- **ON** — adaptive frequency adjustment is enabled at 50% (sets `freq_modified = 50`)
- **OFF** — adaptive frequency adjustment is disabled (sets `freq_modified = 0`)

This maps directly to the "adaptive frequency percentage" field in the RainMachine app.

## How It Works

The integration polls your RainMachine's local API using two independent coordinators:

- **Slow coordinator** (default every 5 min) — weather, forecast, restrictions, rain delay, provision, firmware, zone properties, watering details, irrigation forecast
- **Fast coordinator** (default every 10 s) — zone list, program list, watering queue

**API endpoints used:**

| Endpoint | Data |
|----------|----- |
| `/api/4/auth/login` | Authentication |
| `/api/4/parser` | Weather parser status |
| `/api/4/watering/log/details` | Today's watering summary (all runs including manual), per-zone details, and yesterday's irrigation forecast per program |
| `/api/4/watering/queue` | Currently running zones/programs (remaining seconds, machine duration, watering flag) |
| `/api/4/watering/pause` | Pause all active watering (POST) and check remaining pause time (GET) |
| `/api/4/dailystats/details` | 7-day irrigation forecast per program |
| `/api/4/mixer` | Forecast conditions |
| `/api/4/parser/{id}/data/{startDate}/{nDays}` | Raw hourly parser data — used to compute max daily hail probability |
| `/api/4/zone` | Zone list and status (includes master valve if present) |
| `/api/4/zone/properties` | Zone WaterSense properties per zone (referenceTime, userPercentage, ETcoef) |
| `/api/4/zone/{id}/properties` | Write zone properties per zone (active, ETcoef) |
| `/api/4/zone/{id}/start` | Start a zone for a given duration |
| `/api/4/zone/{id}/stop` | Stop a running zone or cancel a queued zone |
| `/api/4/program` | Program list and status |
| `/api/4/program/{id}` | Read/update program (start time, frequency, duration type, duration adjustment, weather adaptive, adaptive frequency, cycle & soak) |
| `/api/4/restrictions/currently` | Active restrictions |
| `/api/4/restrictions/global` | Global restriction settings |
| `/api/4/restrictions/raindelay` | Rain delay status (GET/POST) |
| `/api/4/provision` | Device info and hardware version |
| `/api/4/machine/update` | Firmware update status |

## Troubleshooting

**"Unable to connect"** — Verify your RainMachine IP and port. Try opening `https://<IP>:8080` in a browser.

**"Invalid password"** — Same password used in the RainMachine app.

**Zone sensors show 0** — Normal if no watering occurred today.

**Zone numbering differs from the RainMachine app** — Your controller likely has a master valve. It appears in the zone list under its own name (e.g. "Master Valve") and can be enabled or disabled in the integration configuration. The app hides it from the numbered zone list; this integration shows it explicitly.

**Statistics graph shows "No statistics found"** — Statistics start collecting after installation; historical data is not available.

**Slow response / timeouts** — Increase the timeout in integration options.

**Zone/program switches not appearing** — Reload the integration from **Settings** → **Devices & Services** → **RainMachine Pro** → **⋮** → **Reload**.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
