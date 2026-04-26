import { Check, Copy } from 'lucide-react';
import {
  type MouseEvent,
  type PointerEvent,
  useCallback,
  useEffect,
  useRef,
  useState
} from 'react';

import { cn } from '../utils/cn';
import { TooltipRoot, TooltipTrigger, TooltipContent } from './ui/tooltip';

interface TruncatedProps {
  text: string;
  maxW?: string;
  className?: string;
}

type CopyState = 'idle' | 'copied' | 'failed';

export function Truncated({ text, maxW, className }: TruncatedProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const [overflow, setOverflow] = useState(false);
  const [tooltipOpen, setTooltipOpen] = useState(false);
  const [copyState, setCopyState] = useState<CopyState>('idle');

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setOverflow(el.scrollWidth > el.offsetWidth);
  }, [text]);

  const handleOpenChange = useCallback((open: boolean) => {
    setTooltipOpen(open);
    if (!open) setCopyState('idle');
  }, []);

  const handleTooltipClick = useCallback(
    async (e: MouseEvent<HTMLButtonElement>) => {
      e.preventDefault();
      e.stopPropagation();
      const copied = await copyText(text);
      setCopyState(copied ? 'copied' : 'failed');
      if (copied) {
        window.setTimeout(() => setTooltipOpen(false), 500);
      }
    },
    [text]
  );

  const stopTooltipPointerDown = useCallback((e: PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const stopTooltipClick = useCallback((e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

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
    <TooltipRoot delayDuration={200} open={tooltipOpen} onOpenChange={handleOpenChange}>
      <TooltipTrigger asChild>{span}</TooltipTrigger>
      <TooltipContent
        className="flex max-w-[520px] items-center gap-2"
        style={{ pointerEvents: 'auto' }}
        onPointerDown={stopTooltipPointerDown}
        onClick={stopTooltipClick}
      >
        <span
          className="min-w-0 max-w-[420px] truncate font-mono text-xs select-text"
          style={{ userSelect: 'text' }}
        >
          {text}
        </span>
        <button
          type="button"
          className="inline-flex shrink-0 items-center gap-1 border-l border-background/25 pl-2 text-[11px] text-background/80 hover:text-background"
          onPointerDown={stopTooltipPointerDown}
          onClick={handleTooltipClick}
        >
          {copyState === 'copied' ? (
            <Check aria-hidden="true" size={12} />
          ) : (
            <Copy aria-hidden="true" size={12} />
          )}
          {copyState === 'copied' ? '已复制' : copyState === 'failed' ? '复制失败' : '点击复制'}
        </button>
      </TooltipContent>
    </TooltipRoot>
  );
}

async function copyText(text: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fall back to execCommand below for browsers that reject Clipboard API in tooltips.
    }
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.top = '-9999px';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, text.length);

  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    textarea.remove();
  }
}
