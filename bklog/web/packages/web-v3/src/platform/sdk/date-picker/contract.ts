export type DatePickerValue = import('@blueking/date-picker-js').DateValue;

/** Plain configuration shared by Vue hosts and the framework-independent SDK. */
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
