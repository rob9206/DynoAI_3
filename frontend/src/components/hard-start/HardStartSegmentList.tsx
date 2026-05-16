import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { CrankSegment } from '@/api/hardStart';

interface HardStartSegmentListProps {
  segments: CrankSegment[];
}

function segmentBadgeVariant(type: CrankSegment['type']): 'default' | 'secondary' | 'destructive' {
  if (type === 'NO_START') {
    return 'destructive';
  }
  if (type === 'CATCH') {
    return 'secondary';
  }
  return 'default';
}

function formatSeconds(value: number): string {
  return `${value.toFixed(2)} s`;
}

export function HardStartSegmentList({ segments }: HardStartSegmentListProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Segments</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Label</TableHead>
              <TableHead>Start</TableHead>
              <TableHead>End</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Notes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {segments.map((segment) => (
              <TableRow key={`${segment.type}-${segment.start_s}-${segment.end_s}`}>
                <TableCell>
                  <Badge variant={segmentBadgeVariant(segment.type)}>{segment.type}</Badge>
                </TableCell>
                <TableCell className="font-medium">{segment.label}</TableCell>
                <TableCell>{formatSeconds(segment.start_s)}</TableCell>
                <TableCell>{formatSeconds(segment.end_s)}</TableCell>
                <TableCell>{formatSeconds(segment.duration_s)}</TableCell>
                <TableCell>{segment.notes ?? 'N/A'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

