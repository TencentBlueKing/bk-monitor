import { createDatePicker } from '@blueking/date-picker-js';
import type { DatePickerState, DatePickerEvents, DatePickerHandle } from './contract';

/** Framework-independent SDK boundary; no second Vue runtime is needed. */
export function mountDatePicker(
  host: HTMLElement,
  initial: DatePickerState,
  events: DatePickerEvents,
): DatePickerHandle {
  const clone = (state: DatePickerState): DatePickerState => ({ ...state, modelValue: [...state.modelValue] });
  const picker = createDatePicker(host, { ...clone(initial), enableFormatClick: true });
  const off = [
    picker.on('update:modelValue', value => events.value(value)),
    picker.on('update:format', format => {
      picker.update({ format });
      events.format(format);
    }),
    picker.on('update:timezone', timezone => {
      picker.update({ timezone });
      events.timezone(timezone);
    }),
  ];
  let destroyed = false;
  return {
    update(state) {
      if (!destroyed) picker.update(clone(state));
    },
    handleShowPanel() {
      if (!destroyed) picker.show();
    },
    handleHidePanel() {
      if (!destroyed) picker.hide();
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      off.forEach(unsubscribe => unsubscribe());
      picker.destroy();
    },
  };
}
