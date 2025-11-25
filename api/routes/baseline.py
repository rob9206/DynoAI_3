"""
One-Pull Baseline™ API routes.
"""

from flask import Blueprint, jsonify, request
import csv
import numpy as np
from pathlib import Path
import json
import logging
from dataclasses import asdict

from baseline.one_pull_baseline import OnePullBaseline
from baseline.models import ValidationSeverity
from services.run_manager import get_run_manager
from io_contracts import safe_path_join, RUNS_ROOT

logger = logging.getLogger(__name__)

baseline_bp = Blueprint('baseline', __name__, url_prefix='/api/baseline')


def load_csv_data(csv_path: str) -> dict:
    """Load CSV data for baseline generation."""
    rpm, map_vals, afr_cmd, afr_meas, torque = [], [], [], [], []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Handle various column name formats
            rpm_val = row.get('RPM') or row.get('rpm') or row.get('ENGINE_RPM')
            map_val = row.get('MAP') or row.get('map') or row.get('MAP_KPA')
            cmd_val = row.get('AFR_COMMANDED') or row.get('afr_commanded') or row.get('AFR_TARGET')
            meas_val = row.get('AFR_MEASURED') or row.get('afr_measured') or row.get('AFR_ACTUAL')
            torque_val = row.get('TORQUE') or row.get('torque')

            if rpm_val and map_val and cmd_val and meas_val:
                rpm.append(float(rpm_val))
                map_vals.append(float(map_val))
                afr_cmd.append(float(cmd_val))
                afr_meas.append(float(meas_val))
                if torque_val:
                    torque.append(float(torque_val))

    return {
        'rpm': np.array(rpm),
        'map': np.array(map_vals),
        'afr_cmd': np.array(afr_cmd),
        'afr_meas': np.array(afr_meas),
        'torque': np.array(torque) if torque else None
    }


@baseline_bp.route('/generate', methods=['POST'])
def generate_baseline():
    """
    Generate One-Pull Baseline from partial-throttle data.

    Request body:
        run_id: string - ID of existing run to use
        OR
        file_path: string - Direct path to CSV file

    Response:
        Full BaselineResult with inline preview data
    """
    data = request.get_json() or {}

    run_id = data.get('run_id')
    file_path = data.get('file_path')

    # Get CSV path
    if run_id:
        manager = get_run_manager()
        csv_path = manager.get_input_csv_path(run_id)
    elif file_path:
        csv_path = Path(file_path)
    else:
        return jsonify({
            'status': 'error',
            'error': {
                'code': 'MISSING_INPUT',
                'message': 'Either run_id or file_path is required'
            }
        }), 400

    if not csv_path.exists():
        return jsonify({
            'status': 'error',
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': f'CSV file not found: {csv_path}'
            }
        }), 404

    try:
        # Load data
        csv_data = load_csv_data(str(csv_path))

        if len(csv_data['rpm']) == 0:
            return jsonify({
                'status': 'error',
                'error': {
                    'code': 'NO_DATA',
                    'message': 'CSV file contains no valid data rows'
                }
            }), 400

        # Generate baseline
        baseline = OnePullBaseline()
        result = baseline.generate(
            rpm_data=csv_data['rpm'],
            map_data=csv_data['map'],
            afr_commanded=csv_data['afr_cmd'],
            afr_measured=csv_data['afr_meas'],
            torque_data=csv_data['torque']
        )

        # Save results if run_id provided
        baseline_id = None
        files = {}

        if run_id:
            baseline_id = f"baseline_{run_id}"
            output_dir = safe_path_join(RUNS_ROOT, run_id, 'baseline')
            output_dir.mkdir(exist_ok=True)

            # Save VE corrections CSV
            ve_path = output_dir / 'baseline_ve.csv'
            with open(ve_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['RPM'] + [str(m) for m in result.map_axis])
                for i, rpm in enumerate(result.rpm_axis):
                    writer.writerow([rpm] + [f"{v:.2f}" for v in result.ve_corrections[i]])
            files['ve_baseline'] = f'/api/download/{run_id}/baseline/baseline_ve.csv'

            # Save confidence CSV
            conf_path = output_dir / 'baseline_confidence.csv'
            with open(conf_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['RPM'] + [str(m) for m in result.map_axis])
                for i, rpm in enumerate(result.rpm_axis):
                    writer.writerow([rpm] + [f"{c:.0f}" for c in result.confidence_map[i]])
            files['confidence_map'] = f'/api/download/{run_id}/baseline/baseline_confidence.csv'

            # Save full diagnostics JSON
            diag_path = output_dir / 'baseline_diagnostics.json'
            with open(diag_path, 'w') as f:
                json.dump({
                    'fdc': asdict(result.fdc),
                    'validation': asdict(result.input_validation),
                    'statistics': {
                        'measured_cells': result.measured_cells,
                        'interpolated_cells': result.interpolated_cells,
                        'extrapolated_cells': result.extrapolated_cells,
                        'avg_confidence': result.avg_confidence,
                        'min_confidence': result.min_confidence
                    }
                }, f, indent=2, default=str)
            files['diagnostics'] = f'/api/download/{run_id}/baseline/baseline_diagnostics.json'

        # Build response with INLINE preview data
        return jsonify({
            'status': 'ok',
            'baseline_id': baseline_id,

            # Summary statistics
            'summary': {
                'measured_cells': result.measured_cells,
                'interpolated_cells': result.interpolated_cells,
                'extrapolated_cells': result.extrapolated_cells,
                'total_cells': result.measured_cells + result.interpolated_cells + result.extrapolated_cells,
                'avg_confidence': result.avg_confidence,
                'min_confidence': result.min_confidence,
                'fdc_value': result.fdc.overall_fdc,
                'fdc_stable': result.fdc.is_stable
            },

            # INLINE preview data for immediate UI rendering
            'preview': {
                've_corrections': result.ve_corrections,
                'confidence_map': result.confidence_map,
                'cell_types': result.cell_types,
                'rpm_axis': result.rpm_axis,
                'map_axis': result.map_axis
            },

            # FDC analysis details
            'fdc_analysis': {
                'overall': result.fdc.overall_fdc,
                'low_map': result.fdc.low_map_fdc,
                'high_map': result.fdc.high_map_fdc,
                'stability_score': result.fdc.stability_score,
                'is_stable': result.fdc.is_stable
            },

            # Validation issues
            'validation': {
                'is_valid': result.input_validation.is_valid,
                'errors': [
                    {'code': i.code, 'message': i.message, 'details': i.details}
                    for i in result.input_validation.errors
                ],
                'warnings': [
                    {'code': i.code, 'message': i.message, 'details': i.details}
                    for i in result.input_validation.warnings
                ]
            },

            # Warnings and recommendations
            'warnings': result.warnings,
            'recommendations': result.recommendations,

            # File download links (if saved)
            'files': files if files else None
        })

    except ValueError as e:
        return jsonify({
            'status': 'error',
            'error': {
                'code': 'VALIDATION_FAILED',
                'message': str(e)
            }
        }), 400
    except Exception as e:
        logger.exception("Baseline generation failed")
        return jsonify({
            'status': 'error',
            'error': {
                'code': 'GENERATION_FAILED',
                'message': f'Baseline generation failed: {str(e)}'
            }
        }), 500


@baseline_bp.route('/preview', methods=['POST'])
def preview_baseline():
    """
    Preview baseline without saving files.
    Same as generate but doesn't persist.
    """
    # Same logic as generate, just don't save files
    return generate_baseline()
