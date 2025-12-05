import { AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { Anomaly } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';

interface DiagnosticsPanelProps {
  anomalies: Anomaly[];
  correctionDiagnostics?: {
    front?: Record<string, any>;
    rear?: Record<string, any>;
  };
}

export default function DiagnosticsPanel({ anomalies, correctionDiagnostics }: DiagnosticsPanelProps) {
  const getSeverityColor = (score: number) => {
    if (score >= 5) return 'text-destructive';
    if (score >= 3) return 'text-accent';
    return 'text-yellow-500';
  };

  const getSeverityIcon = (score: number) => {
    if (score >= 5) return <AlertTriangle className="h-5 w-5 text-destructive" />;
    if (score >= 3) return <AlertTriangle className="h-5 w-5 text-accent" />;
    return <Info className="h-5 w-5 text-yellow-500" />;
  };

  return (
    <div className="space-y-6">
      {/* Data Quality Summary */}
      {correctionDiagnostics && (
        <Card>
          <CardHeader>
            <CardTitle>Data Quality</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Front Cylinder */}
              {correctionDiagnostics.front && (
                <div>
                  <h4 className="text-sm font-medium text-foreground mb-3">Front Cylinder</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Records:</span>
                      <span className="font-mono">{correctionDiagnostics.front.total_records_processed || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Accepted:</span>
                      <span className="font-mono text-green-500">{correctionDiagnostics.front.accepted_wb || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Rejected (Bad AFR):</span>
                      <span className="font-mono text-destructive">{correctionDiagnostics.front.bad_afr_or_request_afr || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Out of Range:</span>
                      <span className="font-mono text-accent">
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
                  <h4 className="text-sm font-medium text-foreground mb-3">Rear Cylinder</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Records:</span>
                      <span className="font-mono">{correctionDiagnostics.rear.total_records_processed || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Accepted:</span>
                      <span className="font-mono text-green-500">{correctionDiagnostics.rear.accepted_wb || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Rejected (Bad AFR):</span>
                      <span className="font-mono text-destructive">{correctionDiagnostics.rear.bad_afr_or_request_afr || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Out of Range:</span>
                      <span className="font-mono text-accent">
                        {(correctionDiagnostics.rear.temp_out_of_range || 0) + 
                         (correctionDiagnostics.rear.map_out_of_range || 0) + 
                         (correctionDiagnostics.rear.tps_out_of_range || 0)}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Anomalies */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            Anomaly Detection
            {anomalies.length === 0 && (
              <Badge variant="secondary" className="ml-2 text-green-500 bg-green-500/10 hover:bg-green-500/20 border-transparent">
                <CheckCircle className="inline h-3 w-3 mr-1" />
                No anomalies
              </Badge>
            )}
          </CardTitle>
        </CardHeader>

        <CardContent>
          {anomalies.length > 0 ? (
            <div className="space-y-4">
              {anomalies.map((anomaly, index) => (
                <div
                  key={index}
                  className="bg-muted/30 rounded-lg p-4 border border-border hover:border-muted-foreground/20 transition-colors"
                >
                  <div className="flex items-start space-x-3">
                    {getSeverityIcon(anomaly.score)}
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium text-foreground">{anomaly.type}</h4>
                        <span className={`text-sm font-semibold ${getSeverityColor(anomaly.score)}`}>
                          Score: {anomaly.score.toFixed(1)}
                        </span>
                      </div>

                      <p className="text-sm text-muted-foreground mb-3">{anomaly.explanation}</p>

                      {/* Cell/Band Info */}
                      {anomaly.cell && (
                        <div className="text-xs text-muted-foreground/70 mb-2 font-mono">
                          Location: RPM {anomaly.cell.rpm} / {anomaly.cell.kpa} kPa
                        </div>
                      )}
                      {anomaly.cell_band && (
                        <div className="text-xs text-muted-foreground/70 mb-2 font-mono">
                          Band: RPM {anomaly.cell_band.rpm?.join('-')} / {anomaly.cell_band.kpa?.join('-')} kPa
                        </div>
                      )}
                      {anomaly.cells && anomaly.cells.length > 0 && (
                        <div className="text-xs text-muted-foreground/70 mb-2 font-mono">
                          Affected cells: {anomaly.cells.length}
                        </div>
                      )}

                      {/* Recommendations */}
                      {anomaly.next_checks && anomaly.next_checks.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-border">
                          <p className="text-xs font-medium text-muted-foreground mb-2">Recommended Actions:</p>
                          <ul className="text-xs text-muted-foreground space-y-1">
                            {anomaly.next_checks.map((check, idx) => (
                              <li key={idx} className="flex items-start">
                                <span className="text-primary mr-2">•</span>
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
            <p className="text-sm text-muted-foreground">
              No significant anomalies detected in the data. All measurements appear within normal ranges.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
