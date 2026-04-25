import { Search, X } from 'lucide-react';
import { useState } from 'react';

import { Badge } from './Badge';
import { ChoiceInput } from './ChoiceInput';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';

export type FilterValue = string | string[];

export interface FilterField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'multi-select' | 'boolean' | 'combobox';
  options?: Array<{ label: string; value: string }>;
  suggestions?: readonly string[];
  placeholder?: string;
  advanced?: boolean;
}

interface FilterToolbarProps {
  fields: FilterField[];
  values: Record<string, FilterValue>;
  onChange: (key: string, value: FilterValue) => void;
  onSearch: () => void;
  onReset: () => void;
  loading?: boolean;
}

function getFilterDisplayValue(field: FilterField, value: FilterValue): string {
  const values = Array.isArray(value) ? value : value.split(',').filter(Boolean);
  if ((field.type === 'select' || field.type === 'multi-select' || field.type === 'combobox') && field.options) {
    return values
      .map((item) => field.options?.find((o) => o.value === item)?.label ?? item)
      .join(', ');
  }
  if (field.type === 'boolean') {
    const boolValue = values[0] ?? '';
    if (boolValue === 'true') return '是';
    if (boolValue === 'false') return '否';
    return boolValue;
  }
  return Array.isArray(value) ? values.join(', ') : value;
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

  const activeTags = fields.filter((field) => {
    const value = values[field.key];
    if (Array.isArray(value)) return value.length > 0;
    return value !== '' && value !== undefined;
  });

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
            <ChoiceInput
              value={values[field.key] ?? ''}
              options={field.options ?? []}
              placeholder={field.placeholder ?? '全部'}
              onChange={(value) => onChange(field.key, value)}
            />
          </div>
        );
      case 'multi-select':
        return (
          <div className="grid gap-1.5" key={field.key}>
            <Label>{field.label}</Label>
            <ChoiceInput
              mode="multiple"
              allowCustom
              value={values[field.key] ?? []}
              options={field.options ?? []}
              placeholder={field.placeholder ?? '全部'}
              onChange={(value) => onChange(field.key, value)}
            />
          </div>
        );
      case 'boolean':
        return (
          <div className="grid gap-1.5" key={field.key}>
            <Label>{field.label}</Label>
            <ChoiceInput
              value={values[field.key] ?? ''}
              options={[
                { label: '是', value: 'true' },
                { label: '否', value: 'false' }
              ]}
              placeholder="全部"
              onChange={(value) => onChange(field.key, value)}
            />
          </div>
        );
      case 'combobox':
        return (
          <div className="grid gap-1.5" key={field.key}>
            <Label>{field.label}</Label>
            <ChoiceInput
              value={values[field.key] ?? ''}
              options={
                field.options ??
                field.suggestions?.map((item) => ({ label: item, value: item })) ??
                []
              }
              placeholder={field.placeholder ?? '输入或选择'}
              allowCustom
              onChange={(value) => onChange(field.key, value)}
            />
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
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        onSearch();
      }}
    >
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-4">
        {primaryFields.map(renderField)}
        <div className="flex items-end gap-2">
          <Button type="submit" disabled={loading}>
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
    </form>
  );
}
