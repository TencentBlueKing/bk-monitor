import { useEffect, useRef, useState } from 'react';

import { cn } from '../utils/cn';
import { TooltipRoot, TooltipTrigger, TooltipContent } from './ui/tooltip';

interface TruncatedProps {
  text: string;
  maxW?: string;
  className?: string;
}

export function Truncated({ text, maxW, className }: TruncatedProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const [overflow, setOverflow] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setOverflow(el.scrollWidth > el.offsetWidth);
  }, [text]);

  const span = (
    <span
      ref={ref}
      className={cn('block truncate', className)}
      style={maxW ? { maxWidth: maxW } : undefined}
    >
      {text}
    </span>
  );

  if (!overflow) return span;

  return (
    <TooltipRoot delayDuration={200}>
      <TooltipTrigger asChild>{span}</TooltipTrigger>
      <TooltipContent>
        <span className="font-mono text-xs whitespace-nowrap">{text}</span>
      </TooltipContent>
    </TooltipRoot>
  );
}
