# RainMachine Pro for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=yashijoe&repository=ha-rainmachine-pro&category=integration)

A custom Home Assistant integration for **RainMachine** smart irrigation controllers. Connects directly to your RainMachine via its local API — no cloud required.

## Features

- **Local polling** — communicates directly with your RainMachine on your LAN
- **Today's watering summary** — total irrigation duration with statistics support for long-term tracking
- **Per-zone details** — scheduled vs actual duration, start time, and skip reason for each zone
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
7. **Parser configuration** — select which weather parsers generate sensor entities; parsers that have already run are pre-enabled; you can also rename each entity at this step

### Options (post-setup)

Go to **Settings** → **Devices & Services** → **RainMachine Pro** → **Configure** to change:

- Update interval (slow, minutes) and zone/program update interval (fast, seconds)
- Timeout
- Zone names and enabled/disabled state
- Program names and enabled/disabled state
- Weather parsers — enable/disable each parser and rename its entity (list fetched fresh from the device each time)

## Entities

Zone and program names are defined by the user inside the RainMachine app and will appear exactly as configured (e.g., "Front Garden", "Lawn", "Summer Program").

### Sensors

| Entity | Description | Unit | State Class |
|--------|-------------|------|-------------|
| `sensor.rainmachine_today_watering` | Total actual irrigation time today | min | `total` |
| `sensor.rainmachine_rain_delay` | Current rain delay status | — | — |
| `sensor.rainmachine_zone_<n>` | Per-zone watering details | min | `measurement` |
| `sensor.rainmachine_parser_*` | Last run time for each weather parser | — | `timestamp` |
| `sensor.rainmachine_forecast_<n>` | Daily forecast (yesterday through +5 days) | — | — |
| `sensor.<zone>_run_completion_time` | Estimated end time for currently running zone (attributes: `last_run_start`, `last_run_end`, `next_run`) | — | `timestamp` |
| `sensor.<program>_run_completion_time` | Estimated end time for currently running program (attributes: `last_run`, `next_run`) | — | `timestamp` |

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
| `switch.<zone_name>` | Start/stop a zone manually (10 min default) — attributes: `last_run_start`, `last_run_end`, `next_run` (date + time, derived from the program that schedules the zone) |
| `switch.<zone_name>_enabled` | Enable/disable a zone |
| `switch.<program_name>` | Start/stop a program — attributes: `last_run`, `next_run` (date + time) |
| `switch.<program_name>_enabled` | Enable/disable a program |
| `switch.rainmachine_freeze_protection` | Enable/disable freeze protection |
| `switch.rainmachine_extra_water_on_hot_days` | Enable/disable extra watering on hot days |

### Number

| Entity | Description | Range |
|--------|-------------|-------|
| `number.rainmachine_rain_delay_days` | Set rain delay | 0–14 days |

### Select

| Entity | Description | Options |
|--------|-------------|---------|
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

- `user_duration_min` / `user_duration_display` — scheduled duration
- `real_duration_min` / `real_duration_display` — actual duration
- `start_time` — scheduled start time
- `flag` — reason if watering was skipped (e.g., "Water surplus", "Stopped by rain sensor")

**Forecast sensors** include:

- `temperature` / `min_temperature` / `max_temperature` — with display variants
- `rain` / `precipitation_forecast` — actual and forecast rainfall in mm
- `evapotranspiration` — ET0 value in mm
- `condition` / `condition_code` — weather condition string and numeric code

**Rain delay sensor** includes:

- `days_remaining` / `hours_remaining` / `minutes_remaining`
- `seconds_remaining`
- `ends_at` — timestamp when delay expires

## Dashboard Example

```yaml
type: grid
cards:
  - type: heading
    heading: "🚿 Irrigation"
    heading_style: title
    badges:
      - type: entity
        entity: sensor.rainmachine_today_watering
        color: brown
  - type: tile
    entity: sensor.rainmachine_zone_1
    state_content:
      - real_duration_display
      - user_duration_display
      - flag
  - type: tile
    entity: sensor.rainmachine_zone_2
    state_content:
      - real_duration_display
      - user_duration_display
      - flag
  - type: tile
    entity: sensor.rainmachine_zone_3
    state_content:
      - real_duration_display
      - user_duration_display
      - flag
  - type: tile
    entity: sensor.rainmachine_zone_4
    state_content:
      - real_duration_display
      - user_duration_display
      - flag
  - type: heading
    heading: Rain Delay
  - type: entities
    entities:
      - entity: number.rainmachine_rain_delay_days
        name: Delay days
      - entity: sensor.rainmachine_rain_delay
        name: Current status
  - type: heading
    heading: Watering History
  - type: statistics-graph
    entities:
      - sensor.rainmachine_today_watering
    chart_type: bar
    period: day
    days_to_show: 7
    stat_types:
      - max
```

## How It Works

The integration polls your RainMachine's local API using two independent coordinators. All communication happens on your LAN — no cloud services are involved.

- **Slow coordinator** (default every 5 min) — weather parsers, forecast, restrictions, rain delay, provision, firmware update
- **Fast coordinator** (default every 10 s) — zone list, program list, watering queue (used by run switches and run completion time sensors)

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
| `/api/4/program` | Program list and status |
| `/api/4/restrictions/currently` | Active restrictions |
| `/api/4/restrictions/global` | Global restriction settings |
| `/api/4/restrictions/raindelay` | Rain delay status (GET/POST) |
| `/api/4/provision` | Device info and hardware version |
| `/api/4/machine/update` | Firmware update status |

Each API call has an independent timeout — if one endpoint is slow or unreachable, the others still update normally.

## Troubleshooting

**"Unable to connect"** — Verify your RainMachine IP and port. Try opening `https://<IP>:8080` in a browser (accept the self-signed certificate warning).

**"Invalid password"** — The password is the same one you use in the RainMachine app.

**Zone sensors show 0** — If no watering occurred today, zones will show 0 min with flag "No watering today". This is normal.

**Statistics graph shows "No statistics found"** — Statistics start collecting after the integration is installed. Historical data from before installation is not available.

**Slow response / timeouts** — Increase the timeout value in the integration options. The `/watering/log/details` endpoint on some RainMachine models can take 15–20 seconds to respond.

**Zone/program switches not appearing** — Zones and programs are loaded at setup time. If you add new zones or programs in the RainMachine app, reload the integration from **Settings** → **Devices & Services** → **RainMachine Pro** → **⋮** → **Reload**.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
