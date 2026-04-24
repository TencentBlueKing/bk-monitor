import { cva, type VariantProps } from 'class-variance-authority';
import type * as React from 'react';

import { cn } from '../../utils/cn';

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary/10 text-primary',
        secondary: 'border-transparent bg-muted text-muted-foreground',
        success: 'border-transparent bg-emerald-50 text-emerald-700',
        warning: 'border-transparent bg-amber-50 text-amber-700',
        destructive: 'border-transparent bg-rose-50 text-rose-700',
        outline: 'border-border text-foreground'
      }
    },
    defaultVariants: {
      variant: 'default'
    }
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
