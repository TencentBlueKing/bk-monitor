export type DatePickerValue = import('@blueking/date-picker').DateValue;

/** Plain values cross the temporary compat/native runtime boundary; never VNodes. */
export interface DatePickerState {
  modelValue: DatePickerValue;
  behavior: 'normal' | 'simplicity';
  needTimezone: boolean;
  timezone?: string;
  format?: string;
  maxDuration?: number;
}
export interface DatePickerEvents {
  value(value: DatePickerValue): void;
  format(value: string): void;
  timezone(value: string): void;
}
export interface DatePickerHandle {
  update(state: DatePickerState): void;
  handleShowPanel(): void;
  handleHidePanel(): void;
  destroy(): void;
}
