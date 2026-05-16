import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import type { HardStartHypothesis } from '@/api/hardStart';

interface HardStartHypothesesProps {
  hypotheses: HardStartHypothesis[];
}

function confidenceProgress(confidence: number): number {
  return Math.max(0, Math.min(100, confidence * 100));
}

export function HardStartHypotheses({ hypotheses }: HardStartHypothesesProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Ranked Hypotheses</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        {hypotheses.map((hypothesis) => (
          <div
            key={`${hypothesis.rank}-${hypothesis.code}`}
            className="grid gap-3 rounded-lg border p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">#{hypothesis.rank}</Badge>
                <p className="text-sm font-semibold">{hypothesis.label}</p>
              </div>
              <Badge variant="outline">{hypothesis.code}</Badge>
            </div>
            <div className="grid gap-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">Confidence</p>
                <p className="text-xs font-medium">{confidenceProgress(hypothesis.confidence).toFixed(0)}%</p>
              </div>
              <Progress value={confidenceProgress(hypothesis.confidence)} />
            </div>
            <p className="text-sm text-muted-foreground">{hypothesis.evidence}</p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">Recommended Action</Badge>
              <span className="text-sm">{hypothesis.action}</span>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

