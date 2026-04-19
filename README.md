# RainMachine Pro for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=yashijoe&repository=ha-rainmachine-pro&category=integration)

A custom Home Assistant integration for **RainMachine** smart irrigation controllers. Connects directly to your RainMachine via its local API — no cloud required.

## Features

- **Local polling** — communicates directly with your RainMachine on your LAN
- **Today's watering summary** — total irrigation duration with statistics support for long-term tracking
- **Per-zone details** — scheduled vs actual duration, start time, and skip reason for each zone
- **Planned zone durations** — each program switch exposes expected watering duration per active zone (weather-adaptive or fixed); each zone sensor exposes expected duration per program
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
5. **Zone configuration** — enable/disable each zone and customize display names; only enabled zones create entities
6. **Program configuration** — enable/disable each program and customize display names; only enabled programs create entities
7. **Parser configuration** — select which weather parsers generate sensor entities

### Options (post-setup)

Go to **Settings** → **Devices & Services** → **RainMachine Pro** → **Configure** to change update intervals, timeout, zone/program names, and parser configuration.

## Entities

### Sensors

| Entity | Description | Unit | State Class |
|--------|-------------|------|-------------|
| `sensor.rainmachine_today_watering` | Total actual irrigation time today | min | `total` |
| `sensor.rainmachine_today_watering_scheduled` | Total scheduled irrigation time today | min | `total` |
| `sensor.rainmachine_rain_delay` | Current rain delay status | — | — |
| `sensor.rainmachine_zone_<n>` | Per-zone watering details | min | `measurement` |
| `sensor.rainmachine_parser_*` | Last run time for each weather parser | — | `timestamp` |
| `sensor.rainmachine_forecast_<n>` | Daily forecast (yesterday through +5 days) | — | — |
| `sensor.<zone>_run_completion_time` | Estimated end time for currently running zone | — | `timestamp` |
| `sensor.<program>_run_completion_time` | Estimated end time for currently running program | — | `timestamp` |

### Binary Sensors

| Entity | Description |
|--------|-------------|
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
| `switch.<zone_name>` | Start/stop a zone manually (10 min default) — attributes: `last_run_start`, `last_run_end`, `next_run` |
| `switch.<zone_name>_enabled` | Enable/disable a zone |
| `switch.<program_name>` | Start/stop a program — see attributes below |
| `switch.<program_name>_enabled` | Enable/disable a program |
| `switch.rainmachine_freeze_protection` | Enable/disable freeze protection |
| `switch.rainmachine_extra_water_on_hot_days` | Enable/disable extra watering on hot days |

### Number

| Entity | Description | Range |
|--------|-------------|-------|
| `number.rainmachine_rain_delay_days` | Set rain delay | 0–14 days |

### Select

| Entity | Description | Options |
|--------|-------------|----------|
| `select.rainmachine_freeze_protection_temperature` | Freeze protection threshold | −7 °C to +4 °C |

### Button

| Entity | Description |
|--------|-------------|
| `button.rainmachine_reboot` | Reboot the RainMachine controller |

### Update

| Entity | Description |
|--------|-------------|
| `update.rainmachine_firmware` | Firmware update status and trigger |

### Sensor Attributes

**Zone sensors** include:

- `userDuration` / `userDuration_display` — scheduled duration
- `realDuration` / `realDuration_display` — actual duration
- `startTime` — scheduled start time
- `flag` — reason if watering was skipped
- `<program name>` — planned duration in seconds for each program that includes this zone
- `<program name>_type` — `suggested` (weather-adaptive) or `fixed`, translated per HA language

**Program switches** include:

- `enabled` — `on` or `off` (program active state)
- `next_run` / `last_run` — next and last run timestamps
- `start_time` — scheduled start time (HH:MM)
- `frequency` — translated frequency label (e.g. "Daily", "Ogni giorno")
- `<zone name>` — planned duration in seconds for each active zone (integer, compatible with HA statistics)
- `<zone name>_type` — `suggested` (weather-adaptive) or `fixed`, translated per HA language
- `total_duration` — total planned seconds across all active zones

**Forecast sensors** include:

- `temperature` / `min_temperature` / `max_temperature`
- `rain` / `precipitation_forecast` — actual and forecast rainfall in mm
- `EvapoTranspiration` — ET0 value in mm
- `meteocode` / `state_translated`

**Rain delay sensor** includes:

- `days_remaining` / `hours_remaining` / `minutes_remaining` / `seconds_remaining`
- `ends_at`

## How It Works

The integration polls your RainMachine's local API using two independent coordinators:

- **Slow coordinator** (default every 5 min) — weather, forecast, restrictions, rain delay, provision, firmware, zone properties
- **Fast coordinator** (default every 10 s) — zone list, program list, watering queue

**API endpoints used:**

| Endpoint | Data |
|----------|------|
| `/api/4/auth/login` | Authentication |
| `/api/4/parser` | Weather parser status |
| `/api/4/watering/log` | Today's watering summary |
| `/api/4/watering/log/details` | Per-zone watering details |
| `/api/4/watering/queue` | Currently running zones/programs |
| `/api/4/mixer` | Forecast conditions |
| `/api/4/zone` | Zone list and status |
| `/api/4/zone/properties` | Zone WaterSense properties (referenceTime for planned durations) |
| `/api/4/program` | Program list and status |
| `/api/4/restrictions/currently` | Active restrictions |
| `/api/4/restrictions/global` | Global restriction settings |
| `/api/4/restrictions/raindelay` | Rain delay status (GET/POST) |
| `/api/4/provision` | Device info and hardware version |
| `/api/4/machine/update` | Firmware update status |

## Troubleshooting

**"Unable to connect"** — Verify your RainMachine IP and port. Try opening `https://<IP>:8080` in a browser.

**"Invalid password"** — Same password used in the RainMachine app.

**Zone sensors show 0** — Normal if no watering occurred today.

**Statistics graph shows "No statistics found"** — Statistics start collecting after installation; historical data is not available.

**Slow response / timeouts** — Increase the timeout in integration options.

**Zone/program switches not appearing** — Reload the integration from **Settings** → **Devices & Services** → **RainMachine Pro** → **⋮** → **Reload**.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
