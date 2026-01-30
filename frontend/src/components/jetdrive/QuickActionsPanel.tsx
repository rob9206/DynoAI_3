/**
 * QuickActionsPanel - Floating action buttons for coverage guidance
 *
 * Shows contextual suggestions based on current coverage gaps.
 * Auto-dismisses after selection or timeout.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Target, Gauge, Thermometer, X } from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';
import type { CoverageReport } from '../../types/veApplyTypes';

interface QuickAction {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  rpmRange: [number, number];
  mapRange: [number, number];
  color: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: 'wot',
    label: 'WOT',
    icon: Target,
    description: 'Full throttle pulls 3000-6000 RPM',
    rpmRange: [3000, 6000],
    mapRange: [95, 105],
    color: 'text-red-400 border-red-500/30 hover:bg-red-500/10',
  },
  {
    id: 'cruise',
    label: 'CRUISE',
    icon: Gauge,
    description: 'Steady-state 2000-4500 RPM, 40-70 kPa',
    rpmRange: [2000, 4500],
    mapRange: [40, 70],
    color: 'text-green-400 border-green-500/30 hover:bg-green-500/10',
  },
  {
    id: 'cold',
    label: 'COLD',
    icon: Thermometer,
    description: 'Cold start and idle data',
    rpmRange: [800, 1500],
    mapRange: [20, 40],
    color: 'text-blue-400 border-blue-500/30 hover:bg-blue-500/10',
  },
];

interface QuickActionsPanelProps {
  coverageReport: CoverageReport | null;
  onActionSelect?: (action: QuickAction) => void;
  onDismiss?: () => void;
  className?: string;
}

export function QuickActionsPanel({
  coverageReport,
  onActionSelect,
  onDismiss,
  className,
}: QuickActionsPanelProps) {
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);
  
  // Calculate which zones need coverage
  const suggestedActions = useMemo(() => {
    if (!coverageReport) return QUICK_ACTIONS;
    
    const zoneNeeds: Record<string, number> = {};
    coverageReport.zoneBreakdown.forEach(zone => {
      zoneNeeds[zone.zone] = 100 - zone.coveragePct;
    });
    
    // Prioritize actions based on coverage gaps
    return [...QUICK_ACTIONS].sort((a, b) => {
      const aZone = a.id === 'wot' ? 'wot' : a.id === 'cruise' ? 'cruise' : 'edge';
      const bZone = b.id === 'wot' ? 'wot' : b.id === 'cruise' ? 'cruise' : 'edge';
      return (zoneNeeds[bZone] ?? 0) - (zoneNeeds[aZone] ?? 0);
    });
  }, [coverageReport]);
  
  // Auto-dismiss after selection
  useEffect(() => {
    if (selectedAction) {
      const timer = setTimeout(() => {
        setSelectedAction(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [selectedAction]);
  
  const handleActionClick = (action: QuickAction) => {
    setSelectedAction(action.id);
    onActionSelect?.(action);
  };
  
  if (dismissed) return null;
  
  return (
    <div className={cn(
      "fixed right-4 top-1/2 -translate-y-1/2 z-50 flex flex-col gap-2",
      className
    )}>
      {/* Dismiss button */}
      <button
        onClick={() => {
          setDismissed(true);
          onDismiss?.();
        }}
        className="self-end p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
      
      {suggestedActions.map((action) => {
        const Icon = action.icon;
        const isSelected = selectedAction === action.id;
        
        return (
          <div key={action.id} className="relative">
            <Button
              onClick={() => handleActionClick(action)}
              variant="outline"
              className={cn(
                "w-20 h-20 flex flex-col items-center justify-center gap-1 rounded-xl transition-all",
                action.color,
                isSelected && "ring-2 ring-white/20"
              )}
            >
              <Icon className="w-6 h-6" />
              <span className="text-xs font-bold">{action.label}</span>
            </Button>
            
            {/* Expanded info on selection */}
            {isSelected && (
              <div className="absolute right-full mr-2 top-1/2 -translate-y-1/2 w-48 p-3 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl animate-in slide-in-from-right-2">
                <p className="text-sm text-white font-medium mb-1">{action.description}</p>
                <p className="text-xs text-zinc-400">
                  RPM: {action.rpmRange[0]}-{action.rpmRange[1]}
                </p>
                <p className="text-xs text-zinc-400">
                  MAP: {action.mapRange[0]}-{action.mapRange[1]} kPa
                </p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default QuickActionsPanel;
