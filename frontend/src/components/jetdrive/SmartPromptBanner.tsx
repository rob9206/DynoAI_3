/**
 * SmartPromptBanner - Contextual guidance banner for the tuning wizard
 *
 * Shows smart suggestions based on:
 * - Current coverage status
 * - Cylinder balance
 * - Block/warning conditions
 * - Step context
 *
 * Designed to be dismissible and non-intrusive.
 * Voice can announce prompts instead of showing text.
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Lightbulb,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  X,
  Volume2,
  ChevronRight,
} from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';
import type { CoverageReport, BalanceReport, BlockReason } from '../../types/veApplyTypes';
import type { WizardStep } from '../../hooks/useTuningWizard';

export type PromptType = 'suggestion' | 'warning' | 'block' | 'success';

export interface SmartPrompt {
  type: PromptType;
  message: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface SmartPromptBannerProps {
  step: WizardStep;
  coverageReport: CoverageReport | null;
  balanceReport?: BalanceReport | null;
  blockReasons?: BlockReason[];
  warnings?: string[];
  onDismiss?: () => void;
  onActionClick?: (action: string) => void;
  voiceEnabled?: boolean;
  className?: string;
}

const PROMPT_STYLES: Record<PromptType, {
  bg: string;
  border: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
}> = {
  suggestion: {
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
    icon: Lightbulb,
    iconColor: 'text-cyan-400',
  },
  warning: {
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    icon: AlertTriangle,
    iconColor: 'text-yellow-400',
  },
  block: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    icon: XCircle,
    iconColor: 'text-red-400',
  },
  success: {
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    icon: CheckCircle2,
    iconColor: 'text-green-400',
  },
};

export function SmartPromptBanner({
  step,
  coverageReport,
  balanceReport,
  blockReasons = [],
  warnings = [],
  onDismiss,
  onActionClick,
  voiceEnabled = false,
  className,
}: SmartPromptBannerProps) {
  const [dismissed, setDismissed] = useState(false);
  const [currentPromptIdx, setCurrentPromptIdx] = useState(0);

  // Generate prompts based on current state
  const prompts = useMemo((): SmartPrompt[] => {
    const result: SmartPrompt[] = [];

    // Block conditions take priority
    if (blockReasons.length > 0) {
      result.push({
        type: 'block',
        message: blockReasons[0].message,
      });
      return result;
    }

    // Step-specific prompts
    if (step === 'collect') {
      // Coverage suggestions
      if (coverageReport) {
        const lowestZone = [...coverageReport.zoneBreakdown].sort(
          (a, b) => a.coveragePct - b.coveragePct
        )[0];

        if (coverageReport.weightedCoveragePct < 30) {
          result.push({
            type: 'suggestion',
            message: 'Start with some WOT pulls to quickly build coverage.',
            action: {
              label: 'WOT Guide',
              onClick: () => onActionClick?.('wot'),
            },
          });
        } else if (lowestZone && lowestZone.coveragePct < 40) {
          result.push({
            type: 'suggestion',
            message: `${lowestZone.zone} zone needs attention (${lowestZone.coveragePct.toFixed(0)}%)`,
            action: {
              label: `${lowestZone.zone.toUpperCase()} Guide`,
              onClick: () => onActionClick?.(lowestZone.zone),
            },
          });
        } else if (coverageReport.weightedCoveragePct >= 60) {
          result.push({
            type: 'success',
            message: 'Coverage target reached! Ready to analyze.',
          });
        }
      }

      // Balance warnings
      if (balanceReport && !balanceReport.warnings.length && balanceReport.rawSystematicBiasPct) {
        const bias = Math.abs(balanceReport.rawSystematicBiasPct);
        if (bias > 3) {
          result.push({
            type: 'warning',
            message: `Cylinder imbalance detected: ${bias.toFixed(1)}% systematic difference`,
          });
        }
      }
    }

    // Review step prompts
    if (step === 'review') {
      if (warnings.length > 0) {
        result.push({
          type: 'warning',
          message: `${warnings.length} warning${warnings.length > 1 ? 's' : ''} to review before applying`,
        });
      } else {
        result.push({
          type: 'success',
          message: 'Corrections look good! Ready to apply.',
        });
      }
    }

    // Setup step
    if (step === 'setup') {
      result.push({
        type: 'suggestion',
        message: 'Start the simulator or connect to your dyno to begin tuning.',
      });
    }

    return result;
  }, [step, coverageReport, balanceReport, blockReasons, warnings, onActionClick]);

  // Reset on step change
  useEffect(() => {
    setDismissed(false);
    setCurrentPromptIdx(0);
  }, [step]);

  // Cycle through prompts
  const currentPrompt = prompts[currentPromptIdx % prompts.length];

  if (dismissed || !currentPrompt || prompts.length === 0) {
    return null;
  }

  const style = PROMPT_STYLES[currentPrompt.type];
  const Icon = style.icon;

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3 rounded-lg border transition-all",
        style.bg,
        style.border,
        className
      )}
    >
      <Icon className={cn("w-5 h-5 flex-shrink-0", style.iconColor)} />

      <p className="flex-1 text-sm text-zinc-200">{currentPrompt.message}</p>

      {/* Action button */}
      {currentPrompt.action && (
        <Button
          onClick={currentPrompt.action.onClick}
          variant="ghost"
          size="sm"
          className="text-xs"
        >
          {currentPrompt.action.label}
          <ChevronRight className="w-3 h-3 ml-1" />
        </Button>
      )}

      {/* Voice indicator */}
      {voiceEnabled && (
        <Volume2 className="w-4 h-4 text-zinc-500" />
      )}

      {/* Multiple prompts indicator */}
      {prompts.length > 1 && (
        <button
          onClick={() => setCurrentPromptIdx((prev) => prev + 1)}
          className="text-xs text-zinc-500 hover:text-zinc-300"
        >
          {currentPromptIdx + 1}/{prompts.length}
        </button>
      )}

      {/* Dismiss button */}
      <button
        onClick={() => {
          setDismissed(true);
          onDismiss?.();
        }}
        className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export default SmartPromptBanner;
