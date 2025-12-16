import { Award, TrendingUp, AlertCircle, CheckCircle, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { Alert, AlertDescription } from './ui/alert';

export interface ConfidenceReport {
  overall_score: number;
  letter_grade: string;
  grade_description: string;
  component_scores: {
    coverage: {
      score: number;
      weight: string;
      details: {
        well_covered_cells: number;
        total_cells: number;
        coverage_percentage: number;
        threshold_hits: number;
      };
    };
    consistency: {
      score: number;
      weight: string;
      details: {
        average_mad: number;
        mad_samples: number;
      };
    };
    anomalies: {
      score: number;
      weight: string;
      details: {
        total_anomalies: number;
        high_severity: number;
      };
    };
    clamping: {
      score: number;
      weight: string;
      details: {
        clamped_cells: number;
        clamp_percentage: number;
      };
    };
  };
  region_breakdown: {
    [key: string]: {
      coverage_percentage: number;
      cells_covered: number;
      cells_total: number;
      average_mad: number;
    };
  };
  recommendations: string[];
  weak_areas: string[];
  performance: {
    calculation_time_ms: number;
  };
}

interface ConfidenceScoreCardProps {
  confidence: ConfidenceReport;
  className?: string;
}

export default function ConfidenceScoreCard({ confidence, className = '' }: ConfidenceScoreCardProps) {
  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A':
        return 'bg-green-500/10 text-green-500 border-green-500/20';
      case 'B':
        return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      case 'C':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20';
      case 'D':
        return 'bg-red-500/10 text-red-500 border-red-500/20';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-green-500';
    if (score >= 70) return 'text-blue-500';
    if (score >= 50) return 'text-yellow-500';
    return 'text-red-500';
  };

  const getProgressColor = (score: number) => {
    if (score >= 85) return 'bg-green-500';
    if (score >= 70) return 'bg-blue-500';
    if (score >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getRecommendationIcon = (rec: string) => {
    if (rec.toLowerCase().includes('excellent')) return <CheckCircle className="h-4 w-4 text-green-500" />;
    if (rec.toLowerCase().includes('collect more data')) return <TrendingUp className="h-4 w-4 text-blue-500" />;
    if (rec.toLowerCase().includes('inconsistent') || rec.toLowerCase().includes('check')) return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    return <Info className="h-4 w-4 text-muted-foreground" />;
  };

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Award className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle>Tune Confidence Score</CardTitle>
              <CardDescription>Overall tune quality assessment</CardDescription>
            </div>
          </div>
          <Badge className={`text-2xl font-bold px-4 py-2 ${getGradeColor(confidence.letter_grade)}`}>
            {confidence.letter_grade}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Overall Score */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Overall Score</span>
            <span className={`text-3xl font-bold ${getScoreColor(confidence.overall_score)}`}>
              {confidence.overall_score}%
            </span>
          </div>
          <Progress 
            value={confidence.overall_score} 
            className="h-3"
            indicatorClassName={getProgressColor(confidence.overall_score)}
          />
          <p className="text-sm text-muted-foreground">{confidence.grade_description}</p>
        </div>

        {/* Component Scores */}
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-foreground">Score Breakdown</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Coverage */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="bg-muted/30 rounded-lg p-3 border border-border hover:border-muted-foreground/20 transition-colors cursor-help">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase">Coverage</span>
                      <Badge variant="outline" className="text-xs">{confidence.component_scores.coverage.weight}</Badge>
                    </div>
                    <div className="flex items-baseline space-x-2">
                      <span className={`text-2xl font-bold ${getScoreColor(confidence.component_scores.coverage.score)}`}>
                        {confidence.component_scores.coverage.score.toFixed(0)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {confidence.component_scores.coverage.details.coverage_percentage.toFixed(1)}% cells
                      </span>
                    </div>
                    <Progress 
                      value={confidence.component_scores.coverage.score} 
                      className="h-1 mt-2"
                      indicatorClassName={getProgressColor(confidence.component_scores.coverage.score)}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs">
                  <p className="text-xs">
                    {confidence.component_scores.coverage.details.well_covered_cells} of {confidence.component_scores.coverage.details.total_cells} cells 
                    have ≥{confidence.component_scores.coverage.details.threshold_hits} data points
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* Consistency */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="bg-muted/30 rounded-lg p-3 border border-border hover:border-muted-foreground/20 transition-colors cursor-help">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase">Consistency</span>
                      <Badge variant="outline" className="text-xs">{confidence.component_scores.consistency.weight}</Badge>
                    </div>
                    <div className="flex items-baseline space-x-2">
                      <span className={`text-2xl font-bold ${getScoreColor(confidence.component_scores.consistency.score)}`}>
                        {confidence.component_scores.consistency.score.toFixed(0)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        MAD: {confidence.component_scores.consistency.details.average_mad.toFixed(2)}
                      </span>
                    </div>
                    <Progress 
                      value={confidence.component_scores.consistency.score} 
                      className="h-1 mt-2"
                      indicatorClassName={getProgressColor(confidence.component_scores.consistency.score)}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs">
                  <p className="text-xs">
                    Average MAD (Median Absolute Deviation) across {confidence.component_scores.consistency.details.mad_samples} samples.
                    Lower is better.
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* Anomalies */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="bg-muted/30 rounded-lg p-3 border border-border hover:border-muted-foreground/20 transition-colors cursor-help">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase">Anomalies</span>
                      <Badge variant="outline" className="text-xs">{confidence.component_scores.anomalies.weight}</Badge>
                    </div>
                    <div className="flex items-baseline space-x-2">
                      <span className={`text-2xl font-bold ${getScoreColor(confidence.component_scores.anomalies.score)}`}>
                        {confidence.component_scores.anomalies.score.toFixed(0)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {confidence.component_scores.anomalies.details.total_anomalies} found
                      </span>
                    </div>
                    <Progress 
                      value={confidence.component_scores.anomalies.score} 
                      className="h-1 mt-2"
                      indicatorClassName={getProgressColor(confidence.component_scores.anomalies.score)}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs">
                  <p className="text-xs">
                    {confidence.component_scores.anomalies.details.high_severity} high-severity anomalies detected
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* Clamping */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="bg-muted/30 rounded-lg p-3 border border-border hover:border-muted-foreground/20 transition-colors cursor-help">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase">Clamping</span>
                      <Badge variant="outline" className="text-xs">{confidence.component_scores.clamping.weight}</Badge>
                    </div>
                    <div className="flex items-baseline space-x-2">
                      <span className={`text-2xl font-bold ${getScoreColor(confidence.component_scores.clamping.score)}`}>
                        {confidence.component_scores.clamping.score.toFixed(0)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {confidence.component_scores.clamping.details.clamp_percentage.toFixed(1)}% clamped
                      </span>
                    </div>
                    <Progress 
                      value={confidence.component_scores.clamping.score} 
                      className="h-1 mt-2"
                      indicatorClassName={getProgressColor(confidence.component_scores.clamping.score)}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs">
                  <p className="text-xs">
                    {confidence.component_scores.clamping.details.clamped_cells} cells hit correction limits
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        {/* Region Breakdown */}
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-foreground">Region Analysis</h4>
          <div className="space-y-2">
            {Object.entries(confidence.region_breakdown).map(([region, data]) => (
              <div key={region} className="bg-muted/20 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-foreground capitalize">{region}</span>
                  <span className="text-xs text-muted-foreground">
                    {data.cells_covered}/{data.cells_total} cells
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">Coverage: </span>
                    <span className={`font-semibold ${getScoreColor(data.coverage_percentage)}`}>
                      {data.coverage_percentage.toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">MAD: </span>
                    <span className="font-mono">{data.average_mad.toFixed(3)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recommendations */}
        {confidence.recommendations.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground">Recommendations</h4>
            <div className="space-y-2">
              {confidence.recommendations.map((rec, index) => (
                <Alert key={index} className="py-2">
                  <div className="flex items-start space-x-2">
                    {getRecommendationIcon(rec)}
                    <AlertDescription className="text-xs leading-relaxed">
                      {rec}
                    </AlertDescription>
                  </div>
                </Alert>
              ))}
            </div>
          </div>
        )}

        {/* Weak Areas */}
        {confidence.weak_areas.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">Areas Needing More Data</h4>
            <div className="flex flex-wrap gap-2">
              {confidence.weak_areas.map((area, index) => (
                <Badge key={index} variant="outline" className="text-xs">
                  {area}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Performance Footer */}
        <div className="pt-3 border-t border-border">
          <p className="text-xs text-muted-foreground text-center">
            Calculated in {confidence.performance.calculation_time_ms.toFixed(2)}ms
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

