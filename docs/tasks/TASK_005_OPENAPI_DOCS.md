# Task 005: OpenAPI/Swagger Documentation

## Priority: MEDIUM
## Estimated Effort: Medium (2-3 hours)
## Dependencies: None

---

## Objective
Auto-generate interactive API documentation using OpenAPI (Swagger) specification, accessible at `/api/docs`.

## Current State
- No API documentation
- Developers must read code to understand endpoints
- No interactive testing interface

## Target State
- Interactive Swagger UI at `/api/docs`
- Auto-generated from code annotations
- Request/response schemas documented
- Try-it-out functionality for testing

## Implementation Options

### Option A: Flask-RESTX (Recommended)
More integrated with Flask, automatic swagger generation.

### Option B: Flasgger
Simpler, uses YAML docstrings.

---

## Implementation (Flask-RESTX)

### 1. Install Dependencies
Add to `requirements.txt`:
```
flask-restx>=1.3.0
```

### 2. Create `api/docs.py`
```python
"""
DynoAI API Documentation.

Provides OpenAPI/Swagger documentation for the REST API.
"""

from flask import Blueprint
from flask_restx import Api, Resource, fields, Namespace

# Create API documentation
api_bp = Blueprint('api_docs', __name__)
api = Api(
    api_bp,
    version='1.2.0',
    title='DynoAI API',
    description='AI-Powered Dyno Tuning API',
    doc='/docs',
    prefix='/api'
)

# Namespaces
ns_analysis = api.namespace('analyze', description='Analysis operations')
ns_runs = api.namespace('runs', description='Run management')
ns_health = api.namespace('health', description='Health checks')

# Models
error_model = api.model('Error', {
    'code': fields.String(description='Error code'),
    'message': fields.String(description='Error message'),
    'request_id': fields.String(description='Request tracking ID'),
    'details': fields.Raw(description='Additional error details')
})

error_response = api.model('ErrorResponse', {
    'error': fields.Nested(error_model)
})

analysis_params = api.model('AnalysisParams', {
    'smoothPasses': fields.Integer(default=2, description='Number of smoothing passes'),
    'clamp': fields.Float(default=15.0, description='Maximum correction clamp'),
    'rearBias': fields.Float(default=0.0, description='Rear cylinder bias'),
    'rearRuleDeg': fields.Float(default=2.0, description='Rear rule degrees'),
    'hotExtra': fields.Float(default=-1.0, description='Hot extra adjustment')
})

analysis_response = api.model('AnalysisResponse', {
    'run_id': fields.String(description='Unique run identifier'),
    'status': fields.String(description='Initial status (processing)'),
    'message': fields.String(description='Status message')
})

run_status = api.model('RunStatus', {
    'run_id': fields.String(description='Run identifier'),
    'status': fields.String(enum=['pending', 'processing', 'complete', 'error']),
    'progress_percent': fields.Integer(description='Progress percentage (0-100)'),
    'current_stage': fields.String(description='Current processing stage'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp'),
    'error_message': fields.String(description='Error message if failed')
})

file_info = api.model('FileInfo', {
    'name': fields.String(description='File name'),
    'type': fields.String(description='File type'),
    'category': fields.String(description='File category'),
    'size_bytes': fields.Integer(description='File size in bytes')
})

run_detail = api.model('RunDetail', {
    'run_id': fields.String(description='Run identifier'),
    'status': fields.String(description='Run status'),
    'files': fields.List(fields.Nested(file_info), description='Output files'),
    'metadata': fields.Raw(description='Run metadata'),
    'stats': fields.Raw(description='Analysis statistics')
})

health_component = api.model('HealthComponent', {
    'name': fields.String(description='Component name'),
    'status': fields.String(enum=['healthy', 'degraded', 'unhealthy']),
    'message': fields.String(description='Status message'),
    'latency_ms': fields.Float(description='Response latency in ms')
})

health_response = api.model('HealthResponse', {
    'status': fields.String(enum=['healthy', 'degraded', 'unhealthy']),
    'timestamp': fields.DateTime(description='Check timestamp'),
    'version': fields.String(description='API version'),
    'uptime_seconds': fields.Float(description='Server uptime'),
    'components': fields.List(fields.Nested(health_component))
})


# Analysis Endpoints
upload_parser = api.parser()
upload_parser.add_argument('file', location='files', type='file', required=True,
                           help='CSV file with dyno log data')
upload_parser.add_argument('smoothPasses', type=int, default=2, location='form')
upload_parser.add_argument('clamp', type=float, default=15.0, location='form')
upload_parser.add_argument('rearBias', type=float, default=0.0, location='form')


@ns_analysis.route('')
class AnalyzeResource(Resource):
    @ns_analysis.expect(upload_parser)
    @ns_analysis.marshal_with(analysis_response, code=200)
    @ns_analysis.response(400, 'Validation Error', error_response)
    @ns_analysis.response(500, 'Server Error', error_response)
    def post(self):
        """
        Start a new analysis.
        
        Upload a CSV file containing dyno log data to start VE correction analysis.
        Returns a run_id for tracking progress.
        """
        pass  # Actual implementation in app.py


# Runs Endpoints
@ns_runs.route('')
class RunsListResource(Resource):
    @ns_runs.marshal_list_with(run_status)
    def get(self):
        """
        List all analysis runs.
        
        Returns a list of all runs with their current status.
        """
        pass


@ns_runs.route('/<string:run_id>')
@ns_runs.param('run_id', 'The run identifier')
class RunResource(Resource):
    @ns_runs.marshal_with(run_detail)
    @ns_runs.response(404, 'Run not found', error_response)
    def get(self, run_id):
        """
        Get run details.
        
        Returns detailed information about a specific run including output files.
        """
        pass


@ns_runs.route('/<string:run_id>/files/<string:filename>')
@ns_runs.param('run_id', 'The run identifier')
@ns_runs.param('filename', 'The file name to download')
class RunFileResource(Resource):
    @ns_runs.response(200, 'File content')
    @ns_runs.response(404, 'File not found', error_response)
    @ns_runs.produces(['application/octet-stream', 'text/csv', 'application/json'])
    def get(self, run_id, filename):
        """
        Download a run output file.
        
        Returns the requested file from the run's output directory.
        """
        pass


# Health Endpoints
@ns_health.route('')
class HealthResource(Resource):
    @ns_health.marshal_with(health_response)
    def get(self):
        """
        Detailed health check.
        
        Returns comprehensive health status including all component checks.
        """
        pass


@ns_health.route('/live')
class LivenessResource(Resource):
    def get(self):
        """
        Liveness probe.
        
        Simple check that the service is running. Used by Kubernetes liveness probes.
        """
        pass


@ns_health.route('/ready')
class ReadinessResource(Resource):
    def get(self):
        """
        Readiness probe.
        
        Check that the service is ready to handle requests. Used by Kubernetes readiness probes.
        """
        pass
```

### 3. Update `api/app.py`
```python
# Import and register documentation blueprint
from api.docs import api_bp

# Register after other blueprints
app.register_blueprint(api_bp)
```

### 4. Alternative: Flasgger (Simpler)
If you prefer YAML-based documentation:

```python
# In api/app.py
from flasgger import Swagger, swag_from

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/api/apispec.json",
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

swagger = Swagger(app, config=swagger_config)

@app.route("/api/analyze", methods=["POST"])
@swag_from({
    'tags': ['Analysis'],
    'summary': 'Start new analysis',
    'consumes': ['multipart/form-data'],
    'parameters': [
        {
            'name': 'file',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'CSV file with dyno log data'
        }
    ],
    'responses': {
        200: {
            'description': 'Analysis started',
            'schema': {
                'type': 'object',
                'properties': {
                    'run_id': {'type': 'string'},
                    'status': {'type': 'string'}
                }
            }
        }
    }
})
def analyze():
    # ... existing implementation
```

## Acceptance Criteria
- [ ] Swagger UI accessible at `/api/docs`
- [ ] All endpoints documented with descriptions
- [ ] Request parameters documented with types and defaults
- [ ] Response schemas defined
- [ ] Error responses documented
- [ ] Try-it-out functionality works

## Files to Create/Modify
- Create `api/docs.py` (Flask-RESTX) or update `api/app.py` (Flasgger)
- Update `requirements.txt` - add flask-restx or flasgger
- Update `api/app.py` - register documentation blueprint

## Testing
```bash
# Start server
python -m api.app

# Open browser
http://localhost:5000/api/docs
```

