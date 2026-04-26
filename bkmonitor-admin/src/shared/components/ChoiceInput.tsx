import { Check, ChevronDown, Plus } from 'lucide-react';
import { useMemo, useState } from 'react';

import { cn } from '../utils/cn';
import { Badge } from './Badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';

export interface ChoiceOption {
  label: string;
  value: string;
}

interface ChoiceInputProps {
  value?: string | string[];
  options?: ChoiceOption[];
  mode?: 'single' | 'multiple';
  placeholder?: string;
  allowCustom?: boolean;
  disabled?: boolean;
  className?: string;
  contentClassName?: string;
  ariaLabel?: string;
  onChange: (value: string | string[]) => void;
}

export function ChoiceInput({
  value,
  options = [],
  mode = 'single',
  placeholder = '全部',
  allowCustom = false,
  disabled,
  className,
  contentClassName,
  ariaLabel,
  onChange
}: ChoiceInputProps) {
  const [open, setOpen] = useState(false);
  const [customValue, setCustomValue] = useState('');
  const isMultiple = mode === 'multiple';
  const selectedValues = useMemo(() => normalizeValues(value), [value]);
  const optionMap = useMemo(
    () => new Map(options.map((option) => [option.value, option])),
    [options]
  );
  const unknownValues = selectedValues.filter((item) => !optionMap.has(item));
  const displayText = getDisplayText(selectedValues, optionMap, placeholder);

  function emit(nextValues: string[]) {
    if (isMultiple) {
      onChange(nextValues);
      return;
    }

    onChange(nextValues[0] ?? '');
    setOpen(false);
  }

  function toggleValue(nextValue: string) {
    if (!isMultiple) {
      if (selectedValues.includes(nextValue)) {
        emit(['']);
        return;
      }
      emit([nextValue]);
      return;
    }

    if (selectedValues.includes(nextValue)) {
      emit(selectedValues.filter((item) => item !== nextValue));
      return;
    }

    emit([...selectedValues, nextValue]);
  }

  function addCustomValue() {
    const normalizedValue = customValue.trim();
    if (!normalizedValue) return;

    if (isMultiple) {
      emit(
        selectedValues.includes(normalizedValue)
          ? selectedValues
          : [...selectedValues, normalizedValue]
      );
    } else {
      emit([normalizedValue]);
    }
    setCustomValue('');
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          data-choice-trigger
          className={cn('h-10 w-full justify-between px-3 font-normal', className)}
          disabled={disabled}
          aria-label={ariaLabel}
        >
          <span
            className={cn(
              'truncate text-left',
              selectedValues.length === 0 && 'text-muted-foreground'
            )}
          >
            {displayText}
          </span>
          <span className="ml-2 inline-flex items-center gap-1">
            <ChevronDown aria-hidden="true" size={16} className="text-muted-foreground" />
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className={cn('w-[var(--radix-popover-trigger-width)] min-w-52 p-1', contentClassName)}
      >
        <div className="max-h-72 overflow-y-auto py-1">
          {options.map((option) => {
            const selected = selectedValues.includes(option.value);
            return (
              <button
                key={option.value}
                type="button"
                className={cn(
                  'flex w-full items-center gap-2 rounded-sm px-2 py-2 text-left text-sm hover:bg-muted',
                  selected && 'bg-muted'
                )}
                onClick={() => toggleValue(option.value)}
              >
                {isMultiple ? (
                  <span
                    className={cn(
                      'flex size-4 items-center justify-center rounded border border-border',
                      selected && 'border-primary bg-primary text-primary-foreground'
                    )}
                  >
                    {selected ? <Check aria-hidden="true" size={12} /> : null}
                  </span>
                ) : null}
                <span className="min-w-0 flex-1 truncate">{option.label}</span>
                {!isMultiple && selected ? (
                  <Check aria-hidden="true" size={14} className="text-primary" />
                ) : null}
              </button>
            );
          })}
          {unknownValues.map((item) => (
            <button
              key={item}
              type="button"
              className="flex w-full items-center gap-2 rounded-sm bg-muted px-2 py-2 text-left text-sm"
              onClick={() => toggleValue(item)}
            >
              {isMultiple ? (
                <span className="flex size-4 items-center justify-center rounded border border-primary bg-primary text-primary-foreground">
                  <Check aria-hidden="true" size={12} />
                </span>
              ) : null}
              <span className="min-w-0 flex-1 truncate">{item}</span>
              {!isMultiple ? <Check aria-hidden="true" size={14} className="text-primary" /> : null}
            </button>
          ))}
          {options.length === 0 && unknownValues.length === 0 ? (
            <div className="px-2 py-6 text-center text-sm text-muted-foreground">暂无选项</div>
          ) : null}
        </div>

        {allowCustom ? (
          <div className="mt-1 flex gap-2 border-t border-border p-2">
            <Input
              className="h-8"
              value={customValue}
              placeholder="输入原始值"
              onChange={(event) => setCustomValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  addCustomValue();
                }
              }}
            />
            <Button type="button" size="sm" variant="secondary" onClick={addCustomValue}>
              <Plus aria-hidden="true" size={14} />
            </Button>
          </div>
        ) : null}

        {isMultiple && selectedValues.length > 0 ? (
          <div className="flex flex-wrap gap-1 border-t border-border p-2">
            {selectedValues.map((item) => (
              <Badge key={item} tone="muted" className="max-w-full">
                <span className="truncate">{optionMap.get(item)?.label ?? item}</span>
              </Badge>
            ))}
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

function normalizeValues(value: string | string[] | undefined): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => item.trim()).filter(Boolean);
  }
  if (!value) {
    return [];
  }
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function getDisplayText(
  values: string[],
  optionMap: Map<string, ChoiceOption>,
  placeholder: string
) {
  if (values.length === 0) {
    return placeholder;
  }

  return values.map((item) => optionMap.get(item)?.label ?? item).join(', ');
}
