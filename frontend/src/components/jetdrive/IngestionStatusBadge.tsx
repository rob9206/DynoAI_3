/**
 * IngestionStatusBadge - Compact status indicator for ingestion health
 * 
 * Shows a small badge with health status that can be placed in headers
 * or toolbars. Clicking opens a tooltip with more details.
 */

import { useState, useEffect } from 'react';
import {
  Activity, AlertTriangle, CheckCircle2, XCircle, Clock,
  Database, ChevronRight, RefreshCw,
} from 'lucide-react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../ui/popover';
import { Progress } from '../ui/progress';
import { useIngestionHealth } from '../../hooks/useIngestionHealth';
import { getHealthColor, formatDuration } from '../../api/ingestion';

interface IngestionStatusBadgeProps {
  /** Navigate to full health panel */
  onViewDetails?: () => void;
  /** Poll interval */
  pollInterval?: number;
  /** Show text label */
  showLabel?: boolean;
  /** Custom class */
  className?: string;
}

const HealthIcon = ({ health, size = 'sm' }: { health: string; size?: 'sm' | 'md' }) => {
  const sizeClass = size === 'md' ? 'h-4 w-4' : 'h-3 w-3';
  
  switch (health) {
    case 'healthy':
      return <CheckCircle2 className={`${sizeClass} text-green-500`} />;
    case 'warning':
      return <AlertTriangle className={`${sizeClass} text-yellow-500`} />;
    case 'critical':
    case 'unhealthy':
      return <XCircle className={`${sizeClass} text-red-500`} />;
    case 'stale':
      return <Clock className={`${sizeClass} text-gray-500`} />;
    default:
      return <Activity className={`${sizeClass} text-gray-400`} />;
  }
};

export function IngestionStatusBadge({
  onViewDetails,
  pollInterval = 3000,
  showLabel = true,
  className = '',
}: IngestionStatusBadgeProps) {
  const [isOpen, setIsOpen] = useState(false);

  const {
    overallHealth,
    healthyChannels,
    totalChannels,
    frameStats,
    openCircuits,
    isLoading,
    lastUpdate,
    refresh,
  } = useIngestionHealth({ pollInterval, autoStart: true });

  // Pause polling when popover is closed
  const { startPolling, stopPolling } = useIngestionHealth({ autoStart: false });

  useEffect(() => {
    if (isOpen) {
      startPolling();
    }
    return () => stopPolling();
  }, [isOpen, startPolling, stopPolling]);

  const badgeVariant = {
    healthy: 'default',
    warning: 'secondary',
    critical: 'destructive',
    stale: 'outline',
    unknown: 'outline',
  }[overallHealth] || 'outline';

  const healthPercent = totalChannels > 0 ? (healthyChannels / totalChannels) * 100 : 0;
  const hasIssues = overallHealth !== 'healthy' || openCircuits > 0;

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className={`h-8 gap-2 px-2 ${hasIssues ? 'animate-pulse' : ''} ${className}`}
        >
          <div className="relative">
            <Database className={`h-4 w-4 ${getHealthColor(overallHealth)}`} />
            {hasIssues && (
              <span className="absolute -top-1 -right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
              </span>
            )}
          </div>
          {showLabel && (
            <span className={`text-xs ${getHealthColor(overallHealth)}`}>
              {overallHealth === 'healthy' ? 'OK' : overallHealth.toUpperCase()}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent className="w-72 p-4" align="end">
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HealthIcon health={overallHealth} size="md" />
              <span className="font-medium">Ingestion Health</span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => refresh()}
              disabled={isLoading}
              className="h-7 w-7"
            >
              <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          {/* Stats */}
          <div className="space-y-3">
            {/* Channels */}
            <div>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-muted-foreground">Channels</span>
                <span className={getHealthColor(overallHealth)}>
                  {healthyChannels} / {totalChannels}
                </span>
              </div>
              <Progress value={healthPercent} className="h-1.5" />
            </div>

            {/* Frame Rate */}
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Frame Drop Rate</span>
              <span className={frameStats.dropRate > 1 ? 'text-yellow-500' : 'text-green-500'}>
                {frameStats.dropRate.toFixed(2)}%
              </span>
            </div>

            {/* Circuits */}
            {openCircuits > 0 && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Open Circuits</span>
                <Badge variant="destructive" className="text-xs">
                  {openCircuits}
                </Badge>
              </div>
            )}

            {/* Last Update */}
            <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border">
              <span>Updated {formatDuration((Date.now() - lastUpdate) / 1000)} ago</span>
              {onViewDetails && (
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => {
                    setIsOpen(false);
                    onViewDetails();
                  }}
                  className="h-auto p-0 text-xs"
                >
                  View Details
                  <ChevronRight className="h-3 w-3 ml-1" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default IngestionStatusBadge;


