# YourDyno + JetDrive Simulator Removal Notes

Status: removed from active app wiring to simplify JetDrive runtime reliability.

## Why this was removed

- JetDrive command center now runs a single live-data path (`/api/jetdrive/hardware/*`).
- YourDyno dual-source live mode and simulator controls added failure surface and UI complexity.
- The production UI now omits both features to reduce operator error and cross-source state drift.

## Removed frontend runtime wiring

- `frontend/src/pages/JetDriveAutoTunePage.tsx`
  - Removed `useYourDynoLive` stream and source-toggle state.
  - Removed simulator control state/handlers.
  - Removed top-bar Results/History cross-navigation in the JetDrive shell.
- `frontend/src/components/jetdrive/page-sections/JetDriveTopBar.tsx`
  - Removed JetDrive/YourDyno toggle pill.
  - Removed simulator on/off action.
- `frontend/src/components/jetdrive/page-sections/CommandCenterPane.tsx`
  - Removed simulator throttle + trigger-pull strip.
- `frontend/src/components/jetdrive/CommandCenter.tsx`
  - Removed duplicate internal THUNDERHORSE header (single header now comes from `JetDriveTopBar`).

## Removed backend runtime wiring

- Removed YourDyno blueprint registration from `api/app.py`.
- Deleted `api/routes/yourdyno/*`.
- Removed JetDrive simulator blueprint registration in `api/routes/jetdrive/__init__.py`.
- Deleted `api/routes/jetdrive/simulator.py`.

## Service-level cleanup

- Deleted:
  - `api/services/yourdyno/yourdyno_client.py`
  - `api/services/yourdyno/yourdyno_live_queue.py`
- Kept:
  - `api/services/yourdyno/yourdyno_parser.py`
  - `api/services/yourdyno/__init__.py` now exports parser-only symbols for legacy offline parsing paths.

## Endpoint contracts removed from runtime

### YourDyno (removed)

- `GET /api/yourdyno/discover`
- `POST /api/yourdyno/live/start`
- `POST /api/yourdyno/live/stop`
- `GET /api/yourdyno/live/data`
- `GET /api/yourdyno/live/stream`
- `GET /api/yourdyno/live/drain`
- `POST /api/yourdyno/live/reset`
- `GET /api/yourdyno/discover/runs`
- `POST /api/yourdyno/import/parse`
- `GET /api/yourdyno/formats`
- `POST /api/yourdyno/simulator/start`
- `POST /api/yourdyno/simulator/stop`
- `GET /api/yourdyno/simulator/status`
- `POST /api/yourdyno/simulator/pull`
- `POST /api/yourdyno/simulator/throttle`
- `GET /api/yourdyno/simulator/profiles`

### JetDrive simulator (removed)

- `POST /api/jetdrive/simulator/start`
- `POST /api/jetdrive/simulator/stop`
- `GET /api/jetdrive/simulator/status`
- `POST /api/jetdrive/simulator/pull`
- `POST /api/jetdrive/simulator/throttle`
- `POST /api/jetdrive/simulator/load-mode`
- `POST /api/jetdrive/simulator/load-target`
- `POST /api/jetdrive/simulator/rpm-hold`
- `GET /api/jetdrive/simulator/load-state`
- `GET /api/jetdrive/simulator/pull-data`
- `POST /api/jetdrive/simulator/save-pull`
- `GET /api/jetdrive/simulator/profiles`

## Re-implementation checklist (if needed later)

1. Restore `api/routes/yourdyno/*` and re-register `yourdyno_bp` in `api/app.py`.
2. Restore `api/routes/jetdrive/simulator.py` and re-register `simulator_bp` in `api/routes/jetdrive/__init__.py`.
3. Restore `api/services/yourdyno/yourdyno_client.py` and `yourdyno_live_queue.py`.
4. Re-add `frontend/src/hooks/useYourDynoLive.ts`.
5. Re-wire `JetDriveAutoTunePage.tsx` + `JetDriveTopBar.tsx` + `CommandCenterPane.tsx`.
6. Reintroduce integration tests for removed endpoints.

