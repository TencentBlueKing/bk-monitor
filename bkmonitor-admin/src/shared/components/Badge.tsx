import type { PropsWithChildren } from 'react';

import { Badge as UiBadge } from './ui/badge';

interface BadgeProps extends PropsWithChildren {
  tone?: 'default' | 'success' | 'danger' | 'warning' | 'muted';
  className?: string;
  onClick?: () => void;
}

const toneToVariant = {
  default: 'default',
  success: 'success',
  danger: 'destructive',
  warning: 'warning',
  muted: 'secondary'
} as const;

export function Badge({ children, tone = 'default', className, onClick }: BadgeProps) {
  return (
    <UiBadge variant={toneToVariant[tone]} className={className} onClick={onClick}>
      {children}
    </UiBadge>
  );
}
