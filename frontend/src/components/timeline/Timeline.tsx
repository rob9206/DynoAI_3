/**
 * VE Table Time Machine - Timeline Component
 * 
 * Visual timeline showing session history with step-by-step navigation.
 */

import { useState, useMemo } from 'react';
import { Clock, FileText, Search as SearchIcon, Check, Undo2, ChevronLeft, ChevronRight, Play, Pause, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import type { TimelineEvent, TimelineResponse } from '@/api/timeline';
import { formatRelativeTime, getEventTypeLabel } from '@/api/timeline';

// ============================================================================
// Event Type Icons
// ============================================================================

const eventIcons: Record<TimelineEvent['type'], React.ElementType> = {
  baseline: FileText,
  analysis: SearchIcon,
  apply: Check,
  rollback: Undo2,
};

const eventColors: Record<TimelineEvent['type'], string> = {
  baseline: 'bg-slate-500',
  analysis: 'bg-blue-500',
  apply: 'bg-green-500',
  rollback: 'bg-amber-500',
};

// ============================================================================
// Timeline Event Card
// ============================================================================

interface TimelineEventCardProps {
  event: TimelineEvent;
  isActive: boolean;
  onClick: () => void;
}

function TimelineEventCard({ event, isActive, onClick }: TimelineEventCardProps) {
  const Icon = eventIcons[event.type];
  const colorClass = eventColors[event.type];

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-4 rounded-lg border transition-all duration-200',
        'hover:shadow-md hover:border-primary/50',
        isActive
          ? 'border-primary bg-primary/5 shadow-sm'
          : 'border-border bg-card hover:bg-muted/50'
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn('p-2 rounded-lg', colorClass, 'text-white')}>
          <Icon className="h-4 w-4" />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-sm">
              {getEventTypeLabel(event.type)}
            </span>
            <Badge variant="outline" className="text-xs font-mono">
              #{event.sequence}
            </Badge>
          </div>
          
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
            {event.description}
          </p>
          
          <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>{formatRelativeTime(event.timestamp)}</span>
          </div>
        </div>
      </div>
    </button>
  );
}

// ============================================================================
// Timeline Scrubber
// ============================================================================

interface TimelineScrubberProps {
  currentStep: number;
  totalSteps: number;
  events: TimelineEvent[];
  onStepChange: (step: number) => void;
  isPlaying?: boolean;
  onPlayPause?: () => void;
}

function TimelineScrubber({
  currentStep,
  totalSteps,
  events,
  onStepChange,
  isPlaying = false,
  onPlayPause,
}: TimelineScrubberProps) {
  const currentEvent = events[currentStep - 1];

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="space-y-4">
          {/* Current step info */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {currentEvent && (
                <>
                  <div className={cn('p-1.5 rounded', eventColors[currentEvent.type], 'text-white')}>
                    {(() => {
                      const Icon = eventIcons[currentEvent.type];
                      return <Icon className="h-3 w-3" />;
                    })()}
                  </div>
                  <span className="font-medium text-sm">
                    Step {currentStep}: {getEventTypeLabel(currentEvent.type)}
                  </span>
                </>
              )}
            </div>
            <span className="text-sm text-muted-foreground font-mono">
              {currentStep} / {totalSteps}
            </span>
          </div>

          {/* Slider */}
          <Slider
            value={[currentStep]}
            min={1}
            max={totalSteps}
            step={1}
            onValueChange={([value]) => onStepChange(value)}
            className="w-full"
          />

          {/* Controls */}
          <div className="flex items-center justify-center gap-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => onStepChange(Math.max(1, currentStep - 1))}
                    disabled={currentStep <= 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Previous step</TooltipContent>
              </Tooltip>

              {onPlayPause && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={onPlayPause}
                    >
                      {isPlaying ? (
                        <Pause className="h-4 w-4" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{isPlaying ? 'Pause' : 'Play'}</TooltipContent>
                </Tooltip>
              )}

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => onStepChange(Math.min(totalSteps, currentStep + 1))}
                    disabled={currentStep >= totalSteps}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Next step</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Main Timeline Component
// ============================================================================

interface TimelineProps {
  timeline: TimelineResponse;
  currentStep: number;
  onStepChange: (step: number) => void;
  isPlaying?: boolean;
  onPlayPause?: () => void;
  className?: string;
}

export function Timeline({
  timeline,
  currentStep,
  onStepChange,
  isPlaying = false,
  onPlayPause,
  className,
}: TimelineProps) {
  const { events, summary } = timeline;
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<TimelineEvent['type'] | 'all'>('all');

  // Create event index map for O(1) lookups - PERFORMANCE FIX
  const eventIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    events.forEach((event, index) => {
      map.set(event.id, index);
    });
    return map;
  }, [events]);

  // Filter events based on search and type - memoized for performance
  const filteredEvents = useMemo(() => {
    return events.filter(event => {
      const matchesSearch = searchTerm === '' ||
        event.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        event.type.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesType = filterType === 'all' || event.type === filterType;

      return matchesSearch && matchesType;
    });
  }, [events, searchTerm, filterType]);

  if (events.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" />
            Session Timeline
          </CardTitle>
          <CardDescription>No events recorded yet</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-8">
            Operations like analysis, apply, and rollback will appear here as you tune.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header with summary */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Clock className="h-5 w-5 text-primary" />
              Session Timeline
            </CardTitle>
            <div className="flex items-center gap-2">
              {summary.event_counts.analysis > 0 && (
                <Badge variant="secondary" className="gap-1">
                  <SearchIcon className="h-3 w-3" />
                  {summary.event_counts.analysis}
                </Badge>
              )}
              {summary.event_counts.apply > 0 && (
                <Badge variant="secondary" className="gap-1 text-green-600">
                  <Check className="h-3 w-3" />
                  {summary.event_counts.apply}
                </Badge>
              )}
              {summary.event_counts.rollback > 0 && (
                <Badge variant="secondary" className="gap-1 text-amber-600">
                  <Undo2 className="h-3 w-3" />
                  {summary.event_counts.rollback}
                </Badge>
              )}
            </div>
          </div>
          <CardDescription>
            {summary.total_events} operations recorded
          </CardDescription>
        </CardHeader>
        
        {/* Search and Filter */}
        {events.length > 5 && (
          <div className="px-6 pb-3 space-y-2">
            <div className="relative">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search events..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-9 py-2 text-sm border rounded-md bg-background"
                aria-label="Search events"
              />
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            
            <div className="flex gap-2">
              <Button
                variant={filterType === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('all')}
                className="h-7 text-xs"
              >
                All
              </Button>
              <Button
                variant={filterType === 'analysis' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('analysis')}
                className="h-7 text-xs"
              >
                <SearchIcon className="h-3 w-3 mr-1" />
                Analysis
              </Button>
              <Button
                variant={filterType === 'apply' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('apply')}
                className="h-7 text-xs"
              >
                <Check className="h-3 w-3 mr-1" />
                Apply
              </Button>
              <Button
                variant={filterType === 'rollback' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('rollback')}
                className="h-7 text-xs"
              >
                <Undo2 className="h-3 w-3 mr-1" />
                Rollback
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Scrubber */}
      <TimelineScrubber
        currentStep={currentStep}
        totalSteps={events.length}
        events={events}
        onStepChange={onStepChange}
        isPlaying={isPlaying}
        onPlayPause={onPlayPause}
      />

      {/* Event list */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center justify-between">
            <span>Event History</span>
            {filteredEvents.length < events.length && (
              <Badge variant="secondary" className="text-xs">
                {filteredEvents.length} of {events.length}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="max-h-[400px] overflow-y-auto">
          {filteredEvents.length > 0 ? (
            <div className="space-y-2">
              {filteredEvents.map((event) => {
                // Use O(1) map lookup instead of O(n) findIndex - PERFORMANCE FIX
                const actualIndex = eventIndexMap.get(event.id) ?? -1;
                return (
                  <TimelineEventCard
                    key={event.id}
                    event={event}
                    isActive={actualIndex + 1 === currentStep}
                    onClick={() => onStepChange(actualIndex + 1)}
                  />
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground text-sm">
              No events match your search
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default Timeline;

