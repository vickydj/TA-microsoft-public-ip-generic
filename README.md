# Microsoft public ip generic (TA-microsoft-public-ip-generic)

Splunk add-on that downloads Microsoft's published IP range files (Azure service
tags, Microsoft public IP blocks and similar) from the Microsoft Download Center
and indexes them as events. The data is typically used for threat detection,
allow-listing and enrichment of firewall, proxy and cloud logs.

## External data sources

This add-on calls external services over HTTPS (port 443) on every run:

| Host | Purpose |
|---|---|
| `www.microsoft.com` | Download details page `https://www.microsoft.com/en-<region>/download/details.aspx?id=<id>`, used to find the current file link |
| `download.microsoft.com` | The data file itself (JSON, CSV or XML) |
| The **Internet check URL** setting (default `https://www.google.com`) | Optional reachability check before each run. Clear the setting to disable it |

No data is sent to these hosts other than standard HTTPS requests. All requests
use the proxy configured in the add-on, and TLS certificates are verified.

## Version support

| Component | Supported |
|---|---|
| Splunk Enterprise | 9.3 and later (tested on 10.4.1) |
| Python | 3.9, 3.13 (`python.required = 3.9, 3.13`) |
| Splunk Cloud Platform | Passes the Splunk AppInspect cloud checks |
| Platforms | Linux x86_64 and AArch64 (pure Python, no compiled binaries) |

## System requirements

- Install on the Splunk instance that runs the inputs: a heavy forwarder, or a
  single-instance / search head deployment that is allowed to run modular inputs.
- Outbound HTTPS to `www.microsoft.com` and `download.microsoft.com`, directly or
  through an HTTP/SOCKS proxy.
- If your proxy performs TLS inspection, the proxy's CA certificate must be
  trusted by Splunk's Python, because certificate verification is enabled.
- Licence volume: every run indexes the full file again. For example the Azure
  service tags file (id 56519) is about 3,400 events per run.

## Installation

1. In Splunk Web go to **Apps > Manage Apps > Install app from file**, or install
   from Splunkbase.
2. Upload `TA-microsoft-public-ip-generic-<version>.tgz` and restart Splunk if prompted.
3. For distributed deployments, install it on the heavy forwarder that collects
   the data, and on the search heads for the dashboards and field extractions.

## Configuration

### Add-on settings (Configuration page)

| Tab | Setting | Notes |
|---|---|---|
| Proxy | type, host, port, username, password, remote DNS | Proxy password is stored encrypted in Splunk's credential store |
| Logging | log level | Default `INFO` |
| Additional parameters | Internet check URL | URL fetched before each run. Leave it empty to skip the check |

### Inputs (Inputs page > Create New Input)

| Field | Description |
|---|---|
| Name | Unique input name. Events get `source=microsoft://<name>` |
| Interval | Seconds between runs. Microsoft publishes most of these files weekly, so `86400` (daily) is usually enough |
| Index | Destination index |
| Download URL ID | The numeric `id` from `https://www.microsoft.com/en-us/download/details.aspx?id=<id>` |
| File format | `json`, `csv`, `xml` or `raw` |
| URL region | `us` or `in` (language segment of the Microsoft URL) |

Commonly used download IDs (56519, 53602 and 41653 indexed in testing with 1.0.10;
57063 download link verified):

| ID | File | Format | Events per run |
|---|---|---|---|
| 56519 | Azure IP Ranges and Service Tags - Public Cloud (`ServiceTags_Public_<date>.json`) | json | one per service tag (~3,400) |
| 57063 | Azure IP Ranges and Service Tags - US Government Cloud | json | one per service tag |
| 53602 | Microsoft Public IP Space (`msft-public-ips.csv`) | csv | one per prefix (~530) |
| 41653 | Microsoft Azure Datacenter IP Ranges (`PublicIPs_<date>.xml`, legacy) | xml | 1 (all regions in one event) |

## How to run and search

Inputs run on their interval once created. Events use `sourcetype=info:public:ip`
with JSON fields extracted at search time (`KV_MODE = json`):

- **json**: one event per entry in the file's `values` array, e.g. `name`,
  `properties.region`, `properties.addressPrefixes{}`.
- **csv**: one event per row, with the CSV header as field names, e.g. `Prefix`, `Type`.
- **xml**: one event mapping each region name to its list of subnets.
- **raw**: the whole file as one event.

Each run indexes a complete snapshot, so use only the latest run when you build
lookups, for example:

```
index=<your_index> sourcetype=info:public:ip source="microsoft://<input_name>"
| eventstats max(_time) as latest_run
| where _time >= latest_run - 300
| spath path=properties.addressPrefixes{} output=prefix
| mvexpand prefix
| table name properties.region properties.systemService prefix
```

## Troubleshooting

- Add-on log: `$SPLUNK_HOME/var/log/splunk/ta_microsoft_public_ip_generic_microsoft_public_ip.log`
  (`index=_internal sourcetype=tamicrosoftpublicipgeneric:log`).
- **Connection check** dashboard: run results and `internet` / `microsoft` connectivity per host.
- Included alerts: `Exception on finding deep_link | 404` and `Proxy error with Microsoft inputs`.

| Log message | Cause / fix |
|---|---|
| `Internet check to <url> failed` | The check URL is unreachable. Check the proxy settings, or clear the Internet check URL setting |
| `Exception on getting deep_link : 404 ...` | Wrong or retired Download URL ID |
| `Exception on getting deep_link : could not parse ...` | Microsoft changed the download page layout. Please open an issue |
| `Exception while downloading ...` | Download failed: proxy, firewall, or TLS inspection (see System requirements) |
| `Error processing <format> data ...` | The file does not match the selected format. Check the File format setting |
| `CERTIFICATE_VERIFY_FAILED` | A TLS-inspecting proxy's CA is not trusted by Splunk's Python |

## Support

This add-on is community supported. Report issues and questions at
https://github.com/vickydj/TA-microsoft-public-ip-generic/issues

## Development

| What | Where | When |
|---|---|---|
| Lint: committed `local/`, `local.meta`, `*.backup`, bytecode, tokens, `$7$` secrets or private keys; REST endpoints without authentication; Python that turns off TLS verification | `ci/lint.sh` | pre-push hook, CI |
| Python checks (no unit tests): `bin/*.py` compiles and runs on Python 3.9 | `validate.yml` | CI |
| Package for Splunkbase (from the files git tracks; no tests, CI files or dotfiles) | `ci/build.sh` → `dist/` | CI |
| Splunk AppInspect (Splunkbase + Cloud checks) and the Packaging Toolkit (`slim validate`) | `ci/check.sh` | CI |

- **Pull requests and pushes to `main`** run `.github/workflows/validate.yml`. It uploads the package and the
  AppInspect report as a build artifact. Make **Validate Splunk app** a required status check on `main`.
- **Releases**: bump the version in `default/app.conf` (`[launcher]` and `[id]`, and `app.manifest`), add a
  `### <version>` section to the change log below, merge, then `git tag v<version> && git push origin v<version>`.
  `.github/workflows/release.yml` checks the tag matches the app version, builds and checks the package, and
  publishes a GitHub release with the package, `SHA256SUMS` and the AppInspect report. Upload that package to
  Splunkbase.
- **Pre-push hook**: enable once per clone with `git config core.hooksPath ci/hooks`. It runs the lint (about a
  second). `git push --no-verify` skips it.

## Change log

### 1.0.10
- Rebuilt with Splunk Add-on Builder 4.5.4 and Splunk SDK for Python 2.1.1; runs on Python 3.13.
- Inputs log and skip a failed run instead of terminating the input process.
- HTTP status and TLS certificates are verified for the details page and the download.
- The internet check uses the "Internet check URL" setting through the configured proxy
  (replaces the hard-coded 8.8.8.8 check).
- CSV files are parsed with the standard csv parser and the logged event count is correct.
- Events keep the collecting host instead of `localhost`.
- The Download URL ID is validated as numeric.
- Connection check dashboard panels now receive `internet` / `microsoft` status events.
- Removed the unused Account configuration tab.

### 1.0.9
- Add-on Builder 4.3.0 rebuild; Internet check URL setting; connection check dashboard.

### 1.0.7
- Added health checks on the data feed.
- Quick check dashboard.

### 1.0.6
- Added XML parsing support.
- Added alerts to identify exceptions: `Exception on finding deep_link | 404`,
  `Proxy error with Microsoft inputs`.
- Added inputs template for easier use of data feeds.
- Minor changes to pass the Upgrade Readiness App test for Splunk 9.
