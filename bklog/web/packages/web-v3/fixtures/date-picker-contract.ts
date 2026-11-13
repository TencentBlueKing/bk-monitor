import { mountDatePicker } from '../src/platform/sdk/date-picker/native-entry';
import '@blueking/date-picker-js/style.css';
import type { DatePickerState } from '../src/platform/sdk/date-picker/contract';

// Standalone, synthetic configuration: no business API or identifiers.
const state: DatePickerState = { modelValue: ['now-15m', 'now'], behavior: 'simplicity',
  needTimezone: true, timezone: 'UTC', format: 'YYYY-MM-DD HH:mm:ss', maxDuration: 7 * 86400000 };
const record = (event: string, value: unknown) => {
  document.querySelector('#events')!.textContent = JSON.stringify({ event, value });
};
const events = {
  value: (value: DatePickerState['modelValue']) => record('value', value),
  format: (value: string) => record('format', value),
  timezone: (value: string) => record('timezone', value),
};
const simple = mountDatePicker(document.querySelector<HTMLElement>('#simple')!, state, events);
const normal = mountDatePicker(document.querySelector<HTMLElement>('#normal')!, { ...state, behavior: 'normal' }, events);
document.querySelector('#show')!.addEventListener('click', () => simple.handleShowPanel());
document.querySelector('#hide')!.addEventListener('click', () => simple.handleHidePanel());
document.querySelector('#reset')!.addEventListener('click', () => {
  simple.update({ ...state, modelValue: ['now-30m', 'now'] }); record('reset', ['now-30m', 'now']);
});
document.querySelector('#destroy')!.addEventListener('click', () => { simple.destroy(); normal.destroy(); record('destroy', true); });
window.addEventListener('pagehide', () => { simple.destroy(); normal.destroy(); }, { once: true });
