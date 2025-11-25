import { ReactNode } from 'react';
import { Check, AlertTriangle, X, Info, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  icon?: ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  status?: 'success' | 'warning' | 'error' | 'neutral';
  tooltip?: string;
  className?: string;
}

function getStatusIcon(status: MetricCardProps['status']) {
  switch (status) {
    case 'success':
      return <Check className="h-4 w-4 text-green-500" />;
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-amber-500" />;
    case 'error':
      return <X className="h-4 w-4 text-red-500" />;
    default:
      return null;
  }
}

function getTrendIcon(trend: MetricCardProps['trend']) {
  switch (trend) {
    case 'up':
      return <TrendingUp className="h-4 w-4 text-green-500" />;
    case 'down':
      return <TrendingDown className="h-4 w-4 text-red-500" />;
    case 'neutral':
      return <Minus className="h-4 w-4 text-muted-foreground" />;
    default:
      return null;
  }
}

function getStatusBorderColor(status: MetricCardProps['status']) {
  switch (status) {
    case 'success':
      return 'border-l-green-500';
    case 'warning':
      return 'border-l-amber-500';
    case 'error':
      return 'border-l-red-500';
    default:
      return 'border-l-transparent';
  }
}

export function MetricCard({
  label,
  value,
  unit,
  icon,
  trend,
  status = 'neutral',
  tooltip,
  className,
}: MetricCardProps): JSX.Element {
  const statusIcon = getStatusIcon(status);
  const trendIcon = getTrendIcon(trend);
  const borderColor = getStatusBorderColor(status);

  const cardContent = (
    <Card
      className={cn(
        'border-l-4 transition-all duration-200 hover:shadow-md',
        borderColor,
        className
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-foreground">
                {value}
              </span>
              {unit && (
                <span className="text-sm text-muted-foreground">{unit}</span>
              )}
            </div>
            <div className="flex items-center gap-1.5 mt-1">
              {icon && <span className="text-muted-foreground">{icon}</span>}
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            {statusIcon}
            {trendIcon}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (tooltip) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="cursor-help">{cardContent}</div>
        </TooltipTrigger>
        <TooltipContent>
          <p className="flex items-center gap-1">
            <Info className="h-3 w-3" />
            {tooltip}
          </p>
        </TooltipContent>
      </Tooltip>
    );
  }

  return cardContent;
}

export default MetricCard;
