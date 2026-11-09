import { createApp, defineComponent, h, shallowReactive, shallowRef } from 'vue';
import DatePicker from '@blueking/date-picker';
import type { DatePickerState, DatePickerEvents, DatePickerHandle, DatePickerValue } from './contract';

/** All dependencies in this entry are bundled against the same native Vue3 runtime. */
export function mountDatePicker(
  host: HTMLElement,
  initial: DatePickerState,
  events: DatePickerEvents,
): DatePickerHandle {
  const state = shallowReactive({ ...initial, modelValue: [...initial.modelValue] as DatePickerValue });
  const picker = shallowRef<{ handleShowPanel(): void; handleHidePanel(): void }>();
  const app = createApp(
    defineComponent({
      setup: () => () =>
        h(DatePicker, {
          ...state,
          ref: picker,
          enableFormatClick: true,
          'onUpdate:modelValue': (value) => {
            if (value) events.value(value);
          },
          'onUpdate:format': events.format,
          'onUpdate:timezone': events.timezone,
        }),
    }),
  );
  app.mount(host);
  return {
    update(value) {
      Object.assign(state, value, { modelValue: [...value.modelValue] });
    },
    handleShowPanel() {
      picker.value?.handleShowPanel();
    },
    handleHidePanel() {
      picker.value?.handleHidePanel();
    },
    destroy() {
      app.unmount();
    },
  };
}
