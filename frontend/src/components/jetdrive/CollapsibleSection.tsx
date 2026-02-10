/**
 * CollapsibleSection — Reusable collapsible card for Unified Tuning Tab sections.
 * Uses shadcn Card + Radix Collapsible. Optional icon and badge.
 */

import { ChevronDown, ChevronRight, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useState } from "react";

export interface CollapsibleSectionProps {
  title: string;
  icon?: LucideIcon;
  defaultOpen?: boolean;
  badge?: string | number | React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function CollapsibleSection({
  title,
  icon: Icon,
  defaultOpen = true,
  badge,
  children,
  className,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className={cn("bg-zinc-900/50 border-zinc-800", className)}>
        <CollapsibleTrigger asChild>
          <CardHeader
            className="cursor-pointer select-none flex flex-row items-center gap-2 py-4 hover:bg-zinc-800/30 rounded-t-xl transition-colors"
            data-slot="collapsible-section-trigger"
          >
            {open ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
            )}
            {Icon && <Icon className="h-4 w-4 text-muted-foreground shrink-0" />}
            <span className="font-semibold text-sm flex-1 text-left">{title}</span>
            {badge != null && (
              <span className="text-xs text-muted-foreground font-normal">
                {badge}
              </span>
            )}
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-0">{children}</CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
