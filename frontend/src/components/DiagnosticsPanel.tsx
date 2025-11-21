import { AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { Anomaly } from '../lib/api';

interface DiagnosticsPanelProps {
  anomalies: Anomaly[];
  correctionDiagnostics?: {
    front?: Record<string, any>;
    rear?: Record<string, any>;
  };
}

export default function DiagnosticsPanel({ anomalies, correctionDiagnostics }: DiagnosticsPanelProps) {
  const getSeverityColor = (score: number) => {
    if (score >= 5) return 'text-red-500';
    if (score >= 3) return 'text-orange-500';
    return 'text-yellow-500';
  };

  const getSeverityIcon = (score: number) => {
    if (score >= 5) return <AlertTriangle className="h-5 w-5 text-red-500" />;
    if (score >= 3) return <AlertTriangle className="h-5 w-5 text-orange-500" />;
    return <Info className="h-5 w-5 text-yellow-500" />;
  };

  return (
    <div className="space-y-6">
      {/* Data Quality Summary */}
      {correctionDiagnostics && (
        <div className="bg-gray-900/50 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4">Data Quality</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Front Cylinder */}
            {correctionDiagnostics.front && (
              <div>
                <h4 className="text-sm font-medium text-gray-300 mb-3">Front Cylinder</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Total Records:</span>
                    <span className="text-white">{correctionDiagnostics.front.total_records_processed || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Accepted:</span>
                    <span className="text-green-500">{correctionDiagnostics.front.accepted_wb || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Rejected (Bad AFR):</span>
                    <span className="text-red-500">{correctionDiagnostics.front.bad_afr_or_request_afr || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Out of Range:</span>
                    <span className="text-orange-500">
                      {(correctionDiagnostics.front.temp_out_of_range || 0) + 
                       (correctionDiagnostics.front.map_out_of_range || 0) + 
                       (correctionDiagnostics.front.tps_out_of_range || 0)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Rear Cylinder */}
            {correctionDiagnostics.rear && (
              <div>
                <h4 className="text-sm font-medium text-gray-300 mb-3">Rear Cylinder</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Total Records:</span>
                    <span className="text-white">{correctionDiagnostics.rear.total_records_processed || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Accepted:</span>
                    <span className="text-green-500">{correctionDiagnostics.rear.accepted_wb || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Rejected (Bad AFR):</span>
                    <span className="text-red-500">{correctionDiagnostics.rear.bad_afr_or_request_afr || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Out of Range:</span>
                    <span className="text-orange-500">
                      {(correctionDiagnostics.rear.temp_out_of_range || 0) + 
                       (correctionDiagnostics.rear.map_out_of_range || 0) + 
                       (correctionDiagnostics.rear.tps_out_of_range || 0)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Anomalies */}
      <div className="bg-gray-900/50 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">
          Anomaly Detection
          {anomalies.length === 0 && (
            <span className="ml-2 text-sm font-normal text-green-500">
              <CheckCircle className="inline h-4 w-4 mr-1" />
              No anomalies detected
            </span>
          )}
        </h3>

        {anomalies.length > 0 ? (
          <div className="space-y-4">
            {anomalies.map((anomaly, index) => (
              <div
                key={index}
                className="bg-gray-800/50 rounded-lg p-4 border border-gray-700"
              >
                <div className="flex items-start space-x-3">
                  {getSeverityIcon(anomaly.score)}
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium text-white">{anomaly.type}</h4>
                      <span className={`text-sm font-semibold ${getSeverityColor(anomaly.score)}`}>
                        Score: {anomaly.score.toFixed(1)}
                      </span>
                    </div>

                    <p className="text-sm text-gray-300 mb-3">{anomaly.explanation}</p>

                    {/* Cell/Band Info */}
                    {anomaly.cell && (
                      <div className="text-xs text-gray-400 mb-2">
                        Location: RPM {anomaly.cell.rpm} / {anomaly.cell.kpa} kPa
                      </div>
                    )}
                    {anomaly.cell_band && (
                      <div className="text-xs text-gray-400 mb-2">
                        Band: RPM {anomaly.cell_band.rpm?.join('-')} / {anomaly.cell_band.kpa?.join('-')} kPa
                      </div>
                    )}
                    {anomaly.cells && anomaly.cells.length > 0 && (
                      <div className="text-xs text-gray-400 mb-2">
                        Affected cells: {anomaly.cells.length}
                      </div>
                    )}

                    {/* Recommendations */}
                    {anomaly.next_checks && anomaly.next_checks.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-700">
                        <p className="text-xs font-medium text-gray-400 mb-2">Recommended Actions:</p>
                        <ul className="text-xs text-gray-300 space-y-1">
                          {anomaly.next_checks.map((check, idx) => (
                            <li key={idx} className="flex items-start">
                              <span className="text-blue-500 mr-2">•</span>
                              <span>{check}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">
            No significant anomalies detected in the data. All measurements appear within normal ranges.
          </p>
        )}
      </div>
    </div>
  );
}
