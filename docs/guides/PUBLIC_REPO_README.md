# Public Repo Plan (Sanitized)

This project contains real-world dyno tooling and includes **site-specific configuration, logs, and local artifacts** in the private repo.

To create a safe public repo, use the export script:

```powershell
pwsh -File .\scripts\export_public_repo.ps1 -OutputDir public_export -IncludeHardwareIntegration
```

## What gets removed

- `dynoai.db` (local database)
- `jetdrive_log_*.csv` (captured logs)
- `agent_outputs/` (generated snapshots/reports)
- `deepcode_generated/`, `deepcode_lab/` (generated workspaces)
- `mcp_agent.config.yaml`, `mcp_agent.secrets.yaml` (agent tooling config)
- If **hardware integration is disabled**, `config/dynoware_rt150.json` is removed
- If **hardware integration is enabled**, `config/dynoware_rt150.json` is kept but sanitized (see below)

## What gets redacted

Strings like:
- Dyno serial numbers (example: `RT00220413`)
- LAN IPs (example: `192.168.1.115`)
- Site names (example: `Dawson Dynamics`)

are replaced with safe placeholders in the exported repo.

## Hardware integration (public-safe)

When you export with `-IncludeHardwareIntegration`, the exported repo will include `config/dynoware_rt150.json`, but with placeholders like:
- `ip_address`: `192.168.0.100`
- `serial_number`: `RT00000000`
- `location`: `YOUR_SHOP_NAME`

Users should update those values for their dyno/network.

## After export

Create a new empty repo on GitHub (or your provider), then:

```powershell
cd public_export
git branch -M main
git remote add origin <YOUR_PUBLIC_REPO_URL>
git push -u origin main
```

