import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import type * as React from 'react';

import { cn } from '../../utils/cn';

const TooltipProvider = TooltipPrimitive.Provider;
const TooltipRoot = TooltipPrimitive.Root;

function TooltipTrigger({
  asChild = true,
  ...props
}: React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Trigger>) {
  return <TooltipPrimitive.Trigger asChild={asChild} {...props} />;
}

function TooltipContent({
  className,
  sideOffset = 4,
  ...props
}: React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          'z-50 overflow-hidden rounded-md border border-border bg-foreground px-3 py-1.5 text-sm text-background shadow-lg animate-in fade-in-0 zoom-in-95',
          className
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
}

export { TooltipProvider, TooltipRoot, TooltipTrigger, TooltipContent };
