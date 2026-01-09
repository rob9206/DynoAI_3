/**
 * IngestionHealthPanel - Real-time monitoring of data ingestion health
 * 
 * Displays:
 * - Overall health status with visual indicator
 * - Channel health breakdown with color-coded status
 * - Frame drop statistics
 * - Circuit breaker states with manual reset
 * - Data rate metrics
 */

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, AlertTriangle, CheckCircle2, XCircle, RefreshCw,
  Zap, Radio, BarChart3, Shield, ChevronDown, ChevronUp,
  Clock, Database, Wifi, WifiOff, ArrowUpRight, ArrowDownRight,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { useIngestionHealth } from '../../hooks/useIngestionHealth';
import { getHealthColor, getHealthBgColor, formatDuration } from '../../api/ingestion';
import type { ChannelHealth, CircuitBreakerState } from '../../api/ingestion';

interface IngestionHealthPanelProps {
  /** Show compact view */
  compact?: boolean;
  /** Show circuit breaker controls */
  showCircuitBreakers?: boolean;
  /** Poll interval override */
  pollInterval?: number;
  /** Custom class name */
  className?: string;
}

// Health status icons
const HealthIcon = ({ health }: { health: string }) => {
  switch (health) {
    case 'healthy':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case 'critical':
    case 'unhealthy':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'stale':
      return <Clock className="h-4 w-4 text-gray-500" />;
    case 'degraded':
      return <AlertTriangle className="h-4 w-4 text-orange-500" />;
    default:
      return <Activity className="h-4 w-4 text-gray-400" />;
  }
};

// Animated pulse for live data
const LivePulse = ({ active }: { active: boolean }) => (
  <span className="relative flex h-2 w-2">
    {active && (
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
    )}
    <span className={`relative inline-flex rounded-full h-2 w-2 ${active ? 'bg-green-500' : 'bg-gray-500'}`} />
  </span>
);

// Circuit Breaker Card
const CircuitBreakerCard = ({
  name,
  breaker,
  onReset,
}: {
  name: string;
  breaker: CircuitBreakerState;
  onReset: () => void;
}) => {
  const stateColors = {
    closed: 'bg-green-500/20 border-green-500/30 text-green-400',
    open: 'bg-red-500/20 border-red-500/30 text-red-400',
    half_open: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-400',
  };

  const stateIcons = {
    closed: <Shield className="h-4 w-4" />,
    open: <WifiOff className="h-4 w-4" />,
    half_open: <Wifi className="h-4 w-4" />,
  };

  return (
    <div className={`flex items-center justify-between p-3 rounded-lg border ${stateColors[breaker.state]}`}>
      <div className="flex items-center gap-3">
        {stateIcons[breaker.state]}
        <div>
          <div className="font-medium text-sm">{name}</div>
          <div className="text-xs opacity-70">
            {breaker.failure_count} failures • {(breaker.success_rate * 100).toFixed(0)}% success
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-xs capitalize">
          {breaker.state.replace('_', ' ')}
        </Badge>
        {breaker.state === 'open' && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            className="h-7 px-2"
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            Reset
          </Button>
        )}
      </div>
    </div>
  );
};

// Channel Health Row
const ChannelHealthRow = ({ channel }: { channel: ChannelHealth }) => {
  const rateIndicator = channel.samples_per_second > 10
    ? <ArrowUpRight className="h-3 w-3 text-green-500" />
    : channel.samples_per_second > 0
    ? <ArrowDownRight className="h-3 w-3 text-yellow-500" />
    : <Activity className="h-3 w-3 text-gray-500" />;

  return (
    <div className="flex items-center justify-between py-2 px-3 hover:bg-muted/30 rounded">
      <div className="flex items-center gap-2">
        <HealthIcon health={channel.health} />
        <span className="text-sm font-medium">{channel.channel_name}</span>
      </div>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="flex items-center gap-1">
                {rateIndicator}
                {channel.samples_per_second.toFixed(1)} Hz
              </span>
            </TooltipTrigger>
            <TooltipContent>
              <p>{channel.total_samples} total samples</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <span className={`${channel.age_seconds > 5 ? 'text-yellow-500' : ''}`}>
          {formatDuration(channel.age_seconds)} ago
        </span>
        <span className="font-mono w-16 text-right">
          {channel.last_value.toFixed(2)}
        </span>
      </div>
    </div>
  );
};

export function IngestionHealthPanel({
  compact = false,
  showCircuitBreakers = true,
  pollInterval = 10000, // 10 seconds - health checks don't need high frequency
  className = '',
}: IngestionHealthPanelProps) {
  const [channelsExpanded, setChannelsExpanded] = useState(!compact);
  const [circuitsExpanded, setCircuitsExpanded] = useState(false);

  const {
    overallHealth,
    healthyChannels,
    totalChannels,
    channels,
    frameStats,
    circuitBreakers,
    openCircuits,
    isLoading,
    error,
    lastUpdate,
    refresh,
    resetCircuit,
  } = useIngestionHealth({ pollInterval });

  // Sort channels by health (worst first)
  const sortedChannels = useMemo(() => {
    const healthOrder = { critical: 0, unhealthy: 1, warning: 2, stale: 3, invalid: 4, healthy: 5 };
    return Object.values(channels).sort((a, b) => {
      const orderA = healthOrder[a.health as keyof typeof healthOrder] ?? 5;
      const orderB = healthOrder[b.health as keyof typeof healthOrder] ?? 5;
      return orderA - orderB;
    });
  }, [channels]);

  // Health percentage
  const healthPercent = totalChannels > 0 ? (healthyChannels / totalChannels) * 100 : 0;

  // Frame drop severity
  const dropSeverity = frameStats.dropRate > 5
    ? 'critical'
    : frameStats.dropRate > 1
    ? 'warning'
    : 'healthy';

  return (
    <Card className={`bg-gray-900/50 border-gray-700 ${className}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${getHealthBgColor(overallHealth)}`}>
              <Database className={`h-5 w-5 ${getHealthColor(overallHealth)}`} />
            </div>
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                Ingestion Health
                <LivePulse active={!isLoading && overallHealth !== 'unknown'} />
              </CardTitle>
              <CardDescription className="text-xs">
                Real-time data pipeline status
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={`capitalize ${getHealthBgColor(overallHealth)} ${getHealthColor(overallHealth)}`}
            >
              <HealthIcon health={overallHealth} />
              <span className="ml-1">{overallHealth}</span>
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => refresh()}
              disabled={isLoading}
              className="h-8 w-8"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Error display */}
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4" />
              {error}
            </div>
          </div>
        )}

        {/* No data message */}
        {!error && totalChannels === 0 && (
          <div className="p-4 rounded-lg bg-zinc-800/50 border border-zinc-700 text-center">
            <Activity className="h-8 w-8 mx-auto mb-2 text-zinc-500" />
            <p className="text-sm text-zinc-400 font-medium">No Active Data Stream</p>
            <p className="text-xs text-zinc-500 mt-1">
              Start the hardware monitor and begin capturing to see ingestion health metrics.
            </p>
          </div>
        )}

        {/* Quick Stats Row */}
        <div className="grid grid-cols-3 gap-3">
          {/* Channel Health */}
          <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700">
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
              <Radio className="h-3 w-3" />
              Channels
            </div>
            <div className="flex items-baseline gap-1">
              <span className={`text-xl font-bold ${getHealthColor(overallHealth)}`}>
                {healthyChannels}
              </span>
              <span className="text-sm text-muted-foreground">/ {totalChannels}</span>
            </div>
            <Progress
              value={healthPercent}
              className="h-1 mt-2"
            />
          </div>

          {/* Frame Stats */}
          <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700">
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
              <BarChart3 className="h-3 w-3" />
              Frames
            </div>
            <div className="flex items-baseline gap-1">
              <span className={`text-xl font-bold ${getHealthColor(dropSeverity)}`}>
                {frameStats.dropRate.toFixed(1)}%
              </span>
              <span className="text-sm text-muted-foreground">drop</span>
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {frameStats.dropped.toLocaleString()} / {frameStats.total.toLocaleString()}
            </div>
          </div>

          {/* Circuit Breakers */}
          {showCircuitBreakers && (
            <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700">
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                <Zap className="h-3 w-3" />
                Circuits
              </div>
              <div className="flex items-baseline gap-1">
                <span className={`text-xl font-bold ${openCircuits > 0 ? 'text-red-500' : 'text-green-500'}`}>
                  {Object.keys(circuitBreakers).length - openCircuits}
                </span>
                <span className="text-sm text-muted-foreground">
                  / {Object.keys(circuitBreakers).length} active
                </span>
              </div>
              {openCircuits > 0 && (
                <div className="text-xs text-red-400 mt-1">
                  {openCircuits} circuit{openCircuits > 1 ? 's' : ''} open
                </div>
              )}
            </div>
          )}
        </div>

        {/* Channel Details */}
        {!compact && sortedChannels.length > 0 && (
          <Collapsible open={channelsExpanded} onOpenChange={setChannelsExpanded}>
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between h-9 px-3"
              >
                <span className="flex items-center gap-2 text-sm">
                  <Radio className="h-4 w-4" />
                  Channel Details
                </span>
                {channelsExpanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <AnimatePresence>
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-2 max-h-64 overflow-y-auto rounded-lg border border-gray-700 bg-gray-800/30"
                >
                  <div className="divide-y divide-gray-700/50">
                    {sortedChannels.map((channel) => (
                      <ChannelHealthRow
                        key={channel.channel_id}
                        channel={channel}
                      />
                    ))}
                  </div>
                </motion.div>
              </AnimatePresence>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Circuit Breakers */}
        {showCircuitBreakers && Object.keys(circuitBreakers).length > 0 && (
          <Collapsible open={circuitsExpanded} onOpenChange={setCircuitsExpanded}>
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between h-9 px-3"
              >
                <span className="flex items-center gap-2 text-sm">
                  <Shield className="h-4 w-4" />
                  Circuit Breakers
                  {openCircuits > 0 && (
                    <Badge variant="destructive" className="text-xs ml-2">
                      {openCircuits} open
                    </Badge>
                  )}
                </span>
                {circuitsExpanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-2 space-y-2"
              >
                {Object.entries(circuitBreakers).map(([name, breaker]) => (
                  <CircuitBreakerCard
                    key={name}
                    name={name}
                    breaker={breaker}
                    onReset={() => resetCircuit(name)}
                  />
                ))}
              </motion.div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Last Update */}
        <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          Last updated: {lastUpdate ? new Date(lastUpdate).toLocaleTimeString() : 'Never'}
        </div>
      </CardContent>
    </Card>
  );
}

export default IngestionHealthPanel;


