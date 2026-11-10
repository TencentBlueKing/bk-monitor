/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { computed, defineComponent, nextTick, ref, watch, type PropType } from 'vue';
import { Empty, Input, Popup } from 'tdesign-vue-next';
import i18n from '@/platform/i18n/i18n';
import './sample-column-select.scss';
export interface SampleColumnOption {
  id: string;
  name: string;
  value?: string;
}
/** V2 permits editing the column number in the trigger while separately searching
 * preview choices. Native Select's filter input replaces that trigger, so keep
 * the two inputs independent and use native Popup/Input/List primitives. */
export default defineComponent({
  name: 'SampleColumnSelect',
  compatConfig: { MODE: 3 },
  props: {
    value: { type: String, default: '' },
    options: { type: Array as PropType<SampleColumnOption[]>, default: () => [] },
  },
  emits: { change: (_value: string) => true },
  setup(props, { emit, slots }) {
    const visible = ref(false),
      search = ref(''),
      active = ref(-1);
    const searchInput = ref<{ focus(): void }>();
    const options = computed(() =>
      props.options.filter((option) => option.name.toLowerCase().includes(search.value.toLowerCase())),
    );
    watch(search, () => {
      active.value = -1;
    });
    function visibility(value: boolean) {
      visible.value = value;
      if (!value) {
        search.value = '';
        active.value = -1;
      }
    }
    function select(option: SampleColumnOption) {
      emit('change', option.id);
      visibility(false);
    }
    async function keyboard(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        visibility(false);
        e.stopPropagation();
        return;
      }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        e.stopPropagation();
        if (!visible.value) {
          visibility(true);
          await nextTick();
          searchInput.value?.focus();
        }
        const length = options.value.length;
        if (length)
          active.value =
            e.key === 'ArrowDown' ? (active.value + 1) % length : active.value <= 0 ? length - 1 : active.value - 1;
      } else if (e.key === 'Enter' && visible.value && options.value[active.value]) {
        e.preventDefault();
        select(options.value[active.value]);
      }
    }
    function content() {
      return (
        <div class='sample-column-panel' onKeydown={keyboard}>
          <Input
            ref={searchInput}
            value={search.value}
            clearable
            placeholder={i18n.t('输入关键字搜索')}
            prefixIcon={() => <i class='bk-icon icon-search' />}
            onChange={(value) => {
              search.value = String(value);
            }}
          />
          <ul class='sample-column-options' role='listbox'>
            {options.value.map((option, index) => (
              <li
                key={option.id}
                role='option'
                aria-selected={props.value === option.id}
                class={{
                  'sample-column-option': true,
                  selected: props.value === option.id,
                  focused: active.value === index,
                }}
                onClick={() => select(option)}
              >
                <span class='overflow-tips' title={`${i18n.t('第{n}行', { n: option.id })} ${option.value || ''}`}>
                  {`${i18n.t('第{n}行', { n: option.id })} ${option.value || ''}`}
                </span>
              </li>
            ))}
            {!options.value.length && <Empty title={i18n.t('bk.exception.searchEmpty')} type='empty' />}
          </ul>
        </div>
      );
    }
    return () => (
      <Popup
        visible={visible.value}
        onVisibleChange={visibility}
        trigger='click'
        placement='bottom-left'
        attach='body'
        overlayInnerStyle={{ padding: 0, width: '320px' }}
        content={content}
      >
        <div class='sample-column-select' onKeydown={keyboard}>
          <div class='sample-column-trigger'>{slots.default?.()}</div>
          <i class={{ 'sample-column-arrow bk-icon icon-angle-down': true, open: visible.value }} />
        </div>
      </Popup>
    );
  },
});
