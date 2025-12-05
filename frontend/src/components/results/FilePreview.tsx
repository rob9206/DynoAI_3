/**
 * FilePreview component - Renders visual previews of output files
 * 
 * Supports:
 * - CSV files: Interactive table with heatmap coloring for VE/correction data
 * - TXT files: Formatted text display with syntax highlighting
 * - JSON files: Syntax-highlighted JSON with collapsible sections
 */

import { useState, useEffect, useMemo } from 'react';
import { AlertCircle, ChevronDown, ChevronRight, FileText, Loader2, Table } from 'lucide-react';
import { getColorForValue, getTextColorForBackground } from '../../lib/colorScale';
import { cn } from '../../lib/utils';

interface FilePreviewProps {
  filename: string;
  content: string | null;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}

interface CSVData {
  headers: string[];
  rows: string[][];
  isNumericGrid: boolean;
}

/**
 * Parse CSV content into structured data
 */
function parseCSV(content: string): CSVData {
  const lines = content.trim().split('\n');
  if (lines.length === 0) {
    return { headers: [], rows: [], isNumericGrid: false };
  }

  const headers = lines[0].split(',').map(h => h.trim());
  const rows = lines.slice(1).map(line => line.split(',').map(cell => cell.trim()));

  // Check if this looks like a VE/correction grid (first column is labels, rest are numeric)
  const isNumericGrid = rows.length > 0 && rows.every(row => {
    return row.slice(1).every(cell => !isNaN(parseFloat(cell)) || cell === '');
  });

  return { headers, rows, isNumericGrid };
}

/**
 * CSV Table with heatmap coloring for numeric values
 */
function CSVPreview({ content }: { content: string }) {
  const { headers, rows, isNumericGrid } = useMemo(() => parseCSV(content), [content]);

  if (headers.length === 0) {
    return (
      <div className="text-muted-foreground text-center py-4">
        Empty CSV file
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-muted/50">
            {headers.map((header, idx) => (
              <th
                key={idx}
                className={cn(
                  "px-3 py-2 text-left font-semibold text-foreground border border-border/50",
                  idx === 0 && isNumericGrid && "bg-primary/10 font-mono"
                )}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIdx) => (
            <tr key={rowIdx} className="hover:bg-muted/30 transition-colors">
              {row.map((cell, cellIdx) => {
                const numValue = parseFloat(cell);
                const isNumeric = !isNaN(numValue) && cellIdx > 0 && isNumericGrid;
                
                // Apply heatmap coloring for numeric values in correction grids
                let bgColor: string | undefined;
                let textColor: string | undefined;
                
                if (isNumeric) {
                  bgColor = getColorForValue(numValue, { neutralRange: 0.3 });
                  textColor = getTextColorForBackground(bgColor);
                }

                return (
                  <td
                    key={cellIdx}
                    className={cn(
                      "px-3 py-2 border border-border/50 font-mono text-xs",
                      cellIdx === 0 && isNumericGrid && "bg-primary/5 font-semibold"
                    )}
                    style={isNumeric ? { 
                      backgroundColor: bgColor,
                      color: textColor,
                    } : undefined}
                  >
                    {isNumeric ? numValue.toFixed(1) : cell}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {isNumericGrid && (
        <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded" style={{ backgroundColor: getColorForValue(-5) }} />
            <span>Lean (negative)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded border border-border" style={{ backgroundColor: 'white' }} />
            <span>Neutral</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded" style={{ backgroundColor: getColorForValue(5) }} />
            <span>Rich (positive)</span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Text file preview with diagnostic highlighting
 */
function TextPreview({ content }: { content: string }) {
  const lines = content.split('\n');

  return (
    <div className="font-mono text-sm bg-muted/30 rounded-lg p-4 overflow-x-auto">
      {lines.map((line, idx) => {
        // Highlight different types of content
        const isHeader = line.includes('Summary') || line.includes('Report') || !line.startsWith('-');
        const isHighlight = line.includes('Max') || line.includes('Min') || line.includes('Avg');
        const isWarning = line.toLowerCase().includes('clamp') || line.toLowerCase().includes('hit');

        return (
          <div
            key={idx}
            className={cn(
              "py-0.5",
              isHeader && !line.startsWith('-') && "font-bold text-foreground mb-1",
              isHighlight && "text-primary",
              isWarning && "text-yellow-500"
            )}
          >
            {line || '\u00A0'}
          </div>
        );
      })}
    </div>
  );
}

/**
 * JSON preview with syntax highlighting and expandable objects
 */
function JSONPreview({ content }: { content: string }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['root']));

  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return (
      <div className="text-destructive text-sm">
        Invalid JSON content
      </div>
    );
  }

  const toggleExpand = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const renderValue = (value: unknown, path: string, indent: number = 0): React.ReactNode => {
    const paddingLeft = indent * 16;

    if (value === null) {
      return <span className="text-muted-foreground">null</span>;
    }

    if (typeof value === 'boolean') {
      return <span className="text-purple-500">{value.toString()}</span>;
    }

    if (typeof value === 'number') {
      return <span className="text-blue-500">{value}</span>;
    }

    if (typeof value === 'string') {
      // Check for severity levels
      const severityColors: Record<string, string> = {
        low: 'text-green-500',
        medium: 'text-yellow-500',
        high: 'text-orange-500',
        critical: 'text-red-500',
      };
      const colorClass = severityColors[value.toLowerCase()] || 'text-green-600';
      return <span className={colorClass}>"{value}"</span>;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return <span className="text-muted-foreground">[]</span>;
      }

      const isExpanded = expanded.has(path);

      return (
        <div>
          <button
            onClick={() => toggleExpand(path)}
            className="inline-flex items-center hover:bg-muted rounded px-1 -ml-1"
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted-foreground" />
            )}
            <span className="text-muted-foreground ml-1">[{value.length}]</span>
          </button>
          {isExpanded && (
            <div className="ml-4 border-l border-border/50 pl-2">
              {value.map((item, idx) => (
                <div key={idx} style={{ paddingLeft }}>
                  <span className="text-muted-foreground mr-2">{idx}:</span>
                  {renderValue(item, `${path}[${idx}]`, indent + 1)}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (typeof value === 'object') {
      const entries = Object.entries(value);
      if (entries.length === 0) {
        return <span className="text-muted-foreground">{'{}'}</span>;
      }

      const isExpanded = expanded.has(path);

      return (
        <div>
          <button
            onClick={() => toggleExpand(path)}
            className="inline-flex items-center hover:bg-muted rounded px-1 -ml-1"
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted-foreground" />
            )}
            <span className="text-muted-foreground ml-1">{'{...}'}</span>
          </button>
          {isExpanded && (
            <div className="ml-4 border-l border-border/50 pl-2">
              {entries.map(([key, val]) => (
                <div key={key} style={{ paddingLeft }}>
                  <span className="text-cyan-600">"{key}"</span>
                  <span className="text-muted-foreground">: </span>
                  {renderValue(val, `${path}.${key}`, indent + 1)}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    return <span>{String(value)}</span>;
  };

  return (
    <div className="font-mono text-sm bg-muted/30 rounded-lg p-4 overflow-x-auto">
      {renderValue(parsed, 'root')}
    </div>
  );
}

/**
 * Main FilePreview component
 */
export function FilePreview({
  filename,
  content,
  isLoading,
  error,
  className,
}: FilePreviewProps) {
  if (isLoading) {
    return (
      <div className={cn("flex items-center justify-center py-8", className)}>
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <span className="ml-2 text-muted-foreground">Loading preview...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("flex items-center justify-center py-8 text-destructive", className)}>
        <AlertCircle className="h-5 w-5 mr-2" />
        <span>Failed to load preview: {error}</span>
      </div>
    );
  }

  if (!content) {
    return (
      <div className={cn("text-center py-8 text-muted-foreground", className)}>
        No content to display
      </div>
    );
  }

  const ext = filename.split('.').pop()?.toLowerCase();

  switch (ext) {
    case 'csv':
      return (
        <div className={className}>
          <CSVPreview content={content} />
        </div>
      );
    case 'json':
      return (
        <div className={className}>
          <JSONPreview content={content} />
        </div>
      );
    case 'txt':
    default:
      return (
        <div className={className}>
          <TextPreview content={content} />
        </div>
      );
  }
}

/**
 * Hook for fetching file content
 */
export function useFileContent(runId: string | undefined, filename: string | undefined) {
  const [content, setContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !filename) {
      setContent(null);
      return;
    }

    const fetchContent = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const { getFileContent } = await import('../../api/jetstream');
        const data = await getFileContent(runId, filename);
        setContent(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load file');
        setContent(null);
      } finally {
        setIsLoading(false);
      }
    };

    void fetchContent();
  }, [runId, filename]);

  return { content, isLoading, error };
}

export default FilePreview;

