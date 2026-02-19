# Scripts Directory Structure

This directory contains various scripts for development, testing, analysis, and deployment.

## Directory Structure

- **analysis/**: Scripts for analyzing dyno runs and data packets.
- **build/**: Build scripts (e.g., PyInstaller).
- **calibration/**: Scripts for AFR/VE calibration.
- **data/**: Scripts for data ingestion and generation.
- **demos/**: Demo scripts and examples.
- **dev/**: Development environment setup and utility scripts.
- **docker/**: Docker-related scripts.
- **extensions/**: Extension management.
- **hardware/**: Hardware interface scripts (Innovate, MTS, Serial).
- **jetdrive/**: JetDrive-specific scripts (discovery, autotune).
- **monitoring/**: Real-time monitoring scripts.
- **test/**: Test runners and integration tests.
- **windows/**: Windows-specific PowerShell/Batch scripts.

## Key Scripts

- `dynoai_standalone.py`: Entry point for the standalone web application (Flask + React).
- `dev/start-dev.bat`: Main script to start the development environment (Backend + Frontend).

### Windows helpers

- `windows/quick-start.bat`: Fast startup (no dependency updates).
- `windows/start-all.bat`: Full startup (includes dependency updates).
- `windows/start-all-verbose.bat`: Full startup with verbose output for troubleshooting.
- `windows/set_ea_path.bat`: Sets `ENALYZER_LIB_DIR` for the current shell session.
- `windows/fix-npm-simple.bat`: Reinstall frontend packages without deleting `node_modules`.
- `windows/fix-npm-error.bat`: Full reinstall (deletes `frontend/node_modules` and reinstalls).
- `windows/fix-npm-error-admin.bat`: Full reinstall with admin-only ownership/delete steps.
