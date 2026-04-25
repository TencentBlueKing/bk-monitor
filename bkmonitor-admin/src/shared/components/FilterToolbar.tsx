import { Search, X } from 'lucide-react';
import { useState } from 'react';

import { Badge } from './Badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select } from './ui/select';

export interface FilterField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'boolean' | 'combobox';
  options?: Array<{ label: string; value: string }>;
  suggestions?: readonly string[];
  placeholder?: string;
  advanced?: boolean;
}

interface FilterToolbarProps {
  fields: FilterField[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onSearch: () => void;
  onReset: () => void;
  loading?: boolean;
}

function getFilterDisplayValue(field: FilterField, value: string): string {
  if (field.type === 'select' && field.options) {
    return field.options.find((o) => o.value === value)?.label ?? value;
  }
  if (field.type === 'boolean') {
    if (value === 'true') return '是';
    if (value === 'false') return '否';
    return value;
  }
  return value;
}

export function FilterToolbar({
  fields,
  values,
  onChange,
  onSearch,
  onReset,
  loading
}: FilterToolbarProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const primaryFields = fields.filter((f) => !f.advanced);
  const advancedFields = fields.filter((f) => f.advanced);

  const activeTags = fields.filter((f) => values[f.key] !== '' && values[f.key] !== undefined);

  function renderField(field: FilterField) {
    switch (field.type) {
      case 'number':
        return (
          <div className="grid gap-1.5" key={field.key}>
            <Label>{field.label}</Label>
            <Input
              inputMode="numeric"
              value={values[field.key] ?? ''}
              placeholder={field.placeholder}
              onChange={(event) => onChange(field.key, event.target.value.replace(/\D/g, ''))}
            />
          </div>
        );
      case 'select':
        return (
          <div className="grid gap-1.5" key={field.key}>
            <Label>{field.label}</Label>
            <Select
              value={values[field.key] ?? ''}
              onChange={(event) => onChange(field.key, event.target.value)}
            >
              <option value="">全部</option>
              {field.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </div>
        );
      case 'boolean':
        return (
          <div className="grid gap-1.5" key={field.key}>
            <Label>{field.label}</Label>
            <Select
              value={values[field.key] ?? ''}
              onChange={(event) => onChange(field.key, event.target.value)}
            >
              <option value="">全部</option>
              <option value="true">是</option>
              <option value="false">否</option>
            </Select>
          </div>
        );
      case 'combobox':
        return (
          <div className="grid gap-1.5" key={field.key}>
            <Label>{field.label}</Label>
            <Input
              list={`${field.key}-list`}
              value={values[field.key] ?? ''}
              placeholder={field.placeholder}
              onChange={(event) => onChange(field.key, event.target.value)}
            />
            {field.suggestions ? (
              <datalist id={`${field.key}-list`}>
                {field.suggestions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            ) : null}
          </div>
        );
      case 'text':
      default:
        return (
          <div className="grid gap-1.5" key={field.key}>
            <Label>{field.label}</Label>
            <Input
              value={values[field.key] ?? ''}
              placeholder={field.placeholder}
              onChange={(event) => onChange(field.key, event.target.value)}
            />
          </div>
        );
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-4">
        {primaryFields.map(renderField)}
        <div className="flex items-end gap-2">
          <Button type="button" onClick={onSearch} disabled={loading}>
            <Search aria-hidden="true" size={16} />
            搜索
          </Button>
          <Button variant="secondary" type="button" onClick={onReset} disabled={loading}>
            重置
          </Button>
        </div>
        {advancedFields.length > 0 ? (
          <Button
            variant="ghost"
            className="ml-auto"
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? '[-]' : '[+]'} 高级筛选
          </Button>
        ) : null}
      </div>

      {showAdvanced && advancedFields.length > 0 ? (
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-4">
          {advancedFields.map(renderField)}
        </div>
      ) : null}

      {activeTags.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {activeTags.map((field) => (
            <Badge
              key={field.key}
              tone="muted"
              className="cursor-pointer gap-1"
              onClick={() => onChange(field.key, '')}
            >
              {field.label}: {getFilterDisplayValue(field, values[field.key] ?? '')}
              <X aria-hidden="true" size={12} />
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}
