"""
DynoAI API Documentation.

Provides OpenAPI/Swagger documentation for the REST API using Flasgger.
"""

from flasgger import Swagger

from dynoai.version import __version__ as DYNOAI_VERSION

# Swagger configuration
SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/api/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
}

# Swagger template with API metadata
SWAGGER_TEMPLATE = {
    "info": {
        "title": "DynoAI API",
        "description": """
**AI-Powered Dyno Tuning API**

This API provides endpoints for:
- **Analysis**: Upload and analyze dyno log CSV files for VE table corrections
- **Run Management**: Track analysis runs and download results
- **Jetstream Integration**: Sync with Jetstream cloud data and stream progress
- **Health Monitoring**: Check service health and component status

## Authentication
Currently, the API does not require authentication. Future versions may add API key support.

## Error Responses
All endpoints return errors in a consistent format:
```json
{
    "error": {
        "code": "NOT_FOUND",
        "message": "Resource not found",
        "request_id": "abc123",
        "details": {}
    }
}
```
        """,
        "version": DYNOAI_VERSION,
        "contact": {
            "name": "DynoAI Support",
            "url": "https://github.com/your-org/dynoai",
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    },
    "host": "",  # Auto-detected
    "basePath": "/",
    "schemes": ["http", "https"],
    "tags": [
        {
            "name": "Health",
            "description": "Health check and monitoring endpoints",
        },
        {
            "name": "Analysis",
            "description": "Upload CSV files and run VE correction analysis",
        },
        {
            "name": "Runs",
            "description": "List and download analysis run results",
        },
        {
            "name": "Jetstream",
            "description": "Jetstream cloud integration for real-time data sync",
        },
    ],
    "definitions": {
        "Error": {
            "type": "object",
            "properties": {
                "error": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Error code",
                            "example": "NOT_FOUND",
                        },
                        "message": {
                            "type": "string",
                            "description": "Human-readable error message",
                            "example": "Resource not found",
                        },
                        "request_id": {
                            "type": "string",
                            "description": "Request tracking ID for debugging",
                            "example": "req_abc123",
                        },
                        "details": {
                            "type": "object",
                            "description": "Additional error details",
                        },
                    },
                },
            },
        },
        "AnalysisParams": {
            "type": "object",
            "properties": {
                "smoothPasses": {
                    "type": "integer",
                    "description": "Number of smoothing passes",
                    "default": 2,
                    "minimum": 0,
                    "maximum": 10,
                },
                "clamp": {
                    "type": "number",
                    "description": "Maximum correction clamp value",
                    "default": 15.0,
                    "minimum": 0,
                    "maximum": 50,
                },
                "rearBias": {
                    "type": "number",
                    "description": "Rear cylinder bias adjustment",
                    "default": 0.0,
                    "minimum": -10,
                    "maximum": 10,
                },
                "rearRuleDeg": {
                    "type": "number",
                    "description": "Rear rule degrees",
                    "default": 2.0,
                },
                "hotExtra": {
                    "type": "number",
                    "description": "Hot extra adjustment",
                    "default": -1.0,
                },
            },
        },
        "AnalysisResponse": {
            "type": "object",
            "properties": {
                "runId": {
                    "type": "string",
                    "description": "Unique run identifier",
                    "example": "550e8400-e29b-41d4-a716-446655440000",
                },
                "status": {
                    "type": "string",
                    "description": "Initial status",
                    "enum": ["queued"],
                    "example": "queued",
                },
                "message": {
                    "type": "string",
                    "description": "Status message",
                    "example": "Analysis started",
                },
            },
        },
        "RunStatus": {
            "type": "object",
            "properties": {
                "runId": {
                    "type": "string",
                    "description": "Run identifier",
                },
                "status": {
                    "type": "string",
                    "enum": ["queued", "running", "completed", "error"],
                    "description": "Current run status",
                },
                "progress": {
                    "type": "integer",
                    "description": "Progress percentage (0-100)",
                    "minimum": 0,
                    "maximum": 100,
                },
                "message": {
                    "type": "string",
                    "description": "Status message",
                },
                "filename": {
                    "type": "string",
                    "description": "Original uploaded filename",
                },
                "error": {
                    "type": "string",
                    "description": "Error message (if status is 'error')",
                },
                "manifest": {
                    "type": "object",
                    "description": "Analysis results manifest (when completed)",
                },
            },
        },
        "RunListItem": {
            "type": "object",
            "properties": {
                "runId": {
                    "type": "string",
                    "description": "Run identifier",
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Run start timestamp",
                },
                "inputFile": {
                    "type": "string",
                    "description": "Original input file path",
                },
            },
        },
        "VEData": {
            "type": "object",
            "properties": {
                "rpm": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "RPM axis values",
                },
                "load": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Load (kPa) axis values",
                },
                "corrections": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                    },
                    "description": "VE correction values (2D matrix)",
                },
                "before": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                    },
                    "description": "VE values before corrections",
                },
                "after": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                    },
                    "description": "VE values after corrections",
                },
            },
        },
        "CoverageData": {
            "type": "object",
            "properties": {
                "front": {
                    "type": "object",
                    "properties": {
                        "rpm": {"type": "array", "items": {"type": "integer"}},
                        "load": {"type": "array", "items": {"type": "integer"}},
                        "data": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "integer"},
                            },
                        },
                    },
                    "description": "Front cylinder coverage data",
                },
                "rear": {
                    "type": "object",
                    "properties": {
                        "rpm": {"type": "array", "items": {"type": "integer"}},
                        "load": {"type": "array", "items": {"type": "integer"}},
                        "data": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "integer"},
                            },
                        },
                    },
                    "description": "Rear cylinder coverage data",
                },
            },
        },
        "DiagnosticsData": {
            "type": "object",
            "properties": {
                "report": {
                    "type": "string",
                    "description": "Diagnostics report text",
                },
                "anomalies": {
                    "type": "object",
                    "description": "Anomaly detection results",
                },
            },
        },
        "HealthResponse": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ok", "degraded", "unhealthy"],
                    "description": "Overall health status",
                    "example": "ok",
                },
                "version": {
                    "type": "string",
                    "description": "API version",
                    "example": DYNOAI_VERSION,
                },
                "app": {
                    "type": "string",
                    "description": "Application name",
                    "example": "DynoAI",
                },
            },
        },
        "JetstreamConfig": {
            "type": "object",
            "properties": {
                "api_url": {
                    "type": "string",
                    "description": "Jetstream API URL",
                    "example": "https://api.jetstream.example.com",
                },
                "api_key": {
                    "type": "string",
                    "description": "API key (masked in responses)",
                    "example": "****...****",
                },
                "poll_interval_seconds": {
                    "type": "integer",
                    "description": "Polling interval in seconds",
                    "default": 30,
                    "minimum": 5,
                    "maximum": 300,
                },
                "auto_process": {
                    "type": "boolean",
                    "description": "Auto-process new runs",
                    "default": True,
                },
                "enabled": {
                    "type": "boolean",
                    "description": "Enable Jetstream integration",
                    "default": False,
                },
            },
        },
        "JetstreamStatus": {
            "type": "object",
            "properties": {
                "connected": {
                    "type": "boolean",
                    "description": "Whether connected to Jetstream API",
                },
                "last_poll": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Last poll timestamp",
                },
                "next_poll": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Next scheduled poll timestamp",
                },
                "pending_runs": {
                    "type": "integer",
                    "description": "Number of pending runs",
                },
                "processing_run": {
                    "type": "string",
                    "description": "Currently processing run ID",
                },
                "error": {
                    "type": "string",
                    "description": "Error message if any",
                },
            },
        },
        "JetstreamRun": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "Unique run identifier",
                    "example": "run_2025-11-25T14-30-00Z-abc123",
                },
                "status": {
                    "type": "string",
                    "enum": [
                        "pending",
                        "downloading",
                        "converting",
                        "validating",
                        "processing",
                        "complete",
                        "error",
                    ],
                    "description": "Run status",
                },
                "source": {
                    "type": "string",
                    "enum": ["jetstream", "manual_upload"],
                    "description": "Run source",
                },
                "jetstream_id": {
                    "type": "string",
                    "description": "Jetstream session ID",
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Creation timestamp",
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Last update timestamp",
                },
                "progress_percent": {
                    "type": "integer",
                    "description": "Progress percentage",
                    "minimum": 0,
                    "maximum": 100,
                },
                "current_stage": {
                    "type": "string",
                    "description": "Current processing stage",
                },
                "error_message": {
                    "type": "string",
                    "description": "Error message if status is 'error'",
                },
            },
        },
        "SyncResponse": {
            "type": "object",
            "properties": {
                "new_runs_found": {
                    "type": "integer",
                    "description": "Number of new runs discovered",
                },
                "run_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of new run IDs",
                },
            },
        },
    },
}


def init_swagger(app):
    """Initialize Swagger documentation for the Flask app."""
    return Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)
