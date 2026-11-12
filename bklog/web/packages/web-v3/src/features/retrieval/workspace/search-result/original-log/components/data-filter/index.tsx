/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import {
  Checkbox as TCheckbox,
  Select as TSelect,
  TagInput as TTagInput,
  Tag as TTag,
  InputNumber as TInputNumber,
} from 'tdesign-vue-next';
import type { TagInputChangeContext } from 'tdesign-vue-next';

import { Button as TButton } from 'tdesign-vue-next';
import { computed, defineComponent, ref, watch, onBeforeUnmount } from 'vue';

import { deepClone, contextHighlightColor } from '@/shared/lib/util';
import useLocale from '@/shared/composables/use-locale';
import { cloneDeep } from 'lodash';
import { createRawTippyOverlay } from '@/shared/global/overlay/index';

import FieldsConfig from './fields-config/index';
import HighlightControl from './highlight-control/index';

import './index.scss';

export default defineComponent({
  emits: ["handle-filter","handleFilter","toggle-poll","togglePoll","fields-config-update","fieldsConfigUpdate","copy","fix-current-row","fixCurrentRow"],

  name: 'DataFilter',
  components: {
    FieldsConfig,
    HighlightControl,
  },
  props: {
    isRealTime: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const fieldConfigRef = ref<any>(null);
    const highlightControlRef = ref<any>(null);
    const filterType = ref('include');
    const filterKey = ref<string[]>([]);
    const catchFilterKey = ref<string[]>([]);
    const ignoreCase = ref(false);
    const highlightList = ref<string[]>([]);
    const colorHighlightList = ref<any[]>([]);
    // 显示前-后行开关
    const intervalSwitcher = ref(true);
    const showType = ref('log');
    const isPolling = ref(true);
    const interval = ref({
      prev: 0,
      next: 0,
    });

    const filterTypeList = [
      { id: 'include', name: t('包含') },
      { id: 'uninclude', name: t('不包含') },
    ];

    const tipColorList = [
      {
        color: '#E1ECFF',
        name: t('默认定位'),
      },
      {
        color: '#FAEEB1',
        name: t('上下文命中'),
      },
      {
        color: '#CBF0DA',
        name: t('新增'),
      },
    ];

    const baseInterval = {
      prev: 0,
      next: 0,
    };

    let fieldConfigPopoverInstance: any = null;

    onBeforeUnmount(() => {
      fieldConfigPopoverInstance?.hide();
      fieldConfigPopoverInstance?.destroy?.();
      fieldConfigPopoverInstance = null;
    });

    watch(ignoreCase, () => {
      emit('handle-filter', 'ignoreCase', ignoreCase.value);
    });

    watch(
      interval,
      () => {
        emit('handle-filter', 'interval', intervalSwitcher.value ? interval.value : baseInterval);
      },
      {
        deep: true,
      },
    );
    const catchColorIndexList = computed(() => colorHighlightList.value.map(item => item.colorIndex));

    const filterLog = () => {
      catchFilterKey.value = [...filterKey.value];
      emit('handle-filter', 'filterKey', filterKey.value);
    };
    const changeLightList = () => {
      // 找出未显示的颜色
      const colorIndex = contextHighlightColor.findIndex((item, index) => !catchColorIndexList.value.includes(index));
      const catchCloneColorList = deepClone(colorHighlightList.value);
      // 给高亮颜色重新赋值
      colorHighlightList.value = highlightList.value.map(item => {
        const notChangeItem = catchCloneColorList.find((cItem: { heightKey: string; }) => cItem.heightKey === item);
        if (notChangeItem) return notChangeItem;
        return {
          heightKey: item,
          colorIndex,
          color: contextHighlightColor[colorIndex],
        };
      });
      emit('handle-filter', 'highlightList', colorHighlightList.value);
    };
    const handleFilterType = (val: string) => {
      filterType.value = val;
      emit('handle-filter', 'filterType', val);
    };
    const handleSelectShowType = (type: string) => {
      showType.value = type;
      emit('handle-filter', 'showType', type);
    };
    const handleChangeIntervalShow = (state: boolean) => {
      intervalSwitcher.value = state;
      emit('handle-filter', 'interval', state ? interval.value : baseInterval);
    };
    // 粘贴过滤条件
    const filterPasteFn = (pasteValue: string) => {
      const trimPasteValue = pasteValue.trim();
      if (!filterKey.value.includes(trimPasteValue)) {
        filterKey.value.push(trimPasteValue);
        filterLog();
      }
      return [];
    };
    // 粘贴高亮条件
    const pasteFn = (pasteValue: string) => {
      const trimPasteValue = pasteValue.trim();
      if (!highlightList.value.includes(trimPasteValue) && highlightList.value.length < 5) {
        highlightList.value.push(trimPasteValue);
        changeLightList();
      }
      return [];
    };
    // The old tag input rejects duplicate custom entries. TDesign emits the
    // proposed list before the consumer accepts it, so retain the old list for
    // duplicate Enter while still emitting the source component's change event.
    const acceptTagChange = (current: string[], proposed: (string | number)[], context: TagInputChangeContext) =>
      context.trigger === 'enter' && current.includes(String(context.item)) ? [...current] : proposed.map(String);

    const handleOpenFieldsConfig = (e: any) => {
      if (!fieldConfigPopoverInstance) {
        fieldConfigPopoverInstance = createRawTippyOverlay(
          e.target,
          {
            allowHTML: true,
            content: fieldConfigRef.value.getDom(),
            placement: 'bottom',
            trigger: 'click',
            maxWidth: 380,
            theme: 'light field-config-popover',
            hideOnClick: false,
            interactive: true,
            arrow: true,
          },
          {
            id: 'retrieve-data-filter-fields',
            type: 'popover',
            group: 'retrieve-data-filter',
            rootSelector: '.tippy-box[data-theme~="field-config-popover"]',
            ignoreSelector: '.bk-select-dropdown-menu, .bk-option',
          },
        );
      }
      fieldConfigPopoverInstance.show();
    };

    const handleTogglePolling = () => {
      isPolling.value = !isPolling.value;
      emit('toggle-poll', isPolling.value);
    };

    const handleFieldConfigSuccess = (list: string[]) => {
      fieldConfigPopoverInstance?.hide();
      emit('fields-config-update', list);
    };

    expose({
      reset: () => {
        isPolling.value = true;
        highlightList.value = [];
        colorHighlightList.value = [];
        interval.value = cloneDeep(baseInterval);
        ignoreCase.value = false;
        filterKey.value = [];
        catchFilterKey.value = [];
        showType.value = 'log';
        filterType.value = 'include';
        intervalSwitcher.value = true;
        fieldConfigPopoverInstance?.hide();
      },
      getHighlightControl: () => highlightControlRef.value,
    });

    return () => (
      <div class='filter-bar-main'>
        <div class='filter-item-top'>
          <div class='filter-main'>
            <TSelect
              class='filter-select-main'
              clearable={false}
              value={filterType.value}
              options={filterTypeList.map(option => ({value: option.id, label: option.name}))}
              onChange={value => handleFilterType(String(value))}
            />
            <TTagInput
              class='filter-key-input'
              placeholder={t('输入关键字进行过滤')}
              value={filterKey.value}
              clearable
              onPaste={({e, pasteValue}) => {
                e.preventDefault();
                filterPasteFn(pasteValue);
              }}
              onChange={(value, context) => {
                filterKey.value = acceptTagChange(filterKey.value, value, context);
                filterLog();
              }}
            />
          </div>
          <div class='highlight-main'>
            <div class='prefix-text'>{t('label-高亮').replace('label-', '')}</div>
            <TTagInput
              class='highlight-tag-input'
              placeholder=''
              max={5}
              onPaste={({e, pasteValue}) => {
                e.preventDefault();
                pasteFn(pasteValue);
              }}
              value={highlightList.value}
              clearable
              valueDisplay={(_h, {value, onClose}) => value.map((item, index) => (
                <TTag
                  key={String(item)}
                  closable
                  class='context-highlight-tag'
                  style={{backgroundColor: colorHighlightList.value.find(color => color.heightKey === item)?.color.light}}
                  onClose={() => onClose(index)}
                >{item}</TTag>
              ))}
              onChange={(value, context) => {
                highlightList.value = acceptTagChange(highlightList.value, value, context);
                changeLightList();
              }}
            />
            {highlightList.value.length > 0 && (
              <HighlightControl
                ref={highlightControlRef}
                lightList={highlightList.value}
                showType={showType.value}
              />
            )}
          </div>
          {props.isRealTime && (
            <div class='realtime-control-main'>
              <div
                class='control-item play-pause'
                onClick={handleTogglePolling}
              >
                {isPolling.value ? <log-icon type='zanting' /> : <log-icon type='bofang' />}
              </div>
              <div
                class='control-item'
                onClick={() => emit('copy')}
              >
                <log-icon type='copy' />
              </div>
            </div>
          )}
        </div>
        <div class='filter-item-bottom'>
          <div class='operate-left'>
            <TCheckbox
              class='context-filter-checkbox'
              style='margin-right: 6px'
              checked={ignoreCase.value}
              onChange={(value: boolean) => {
                ignoreCase.value = value;
              }}
            />
            <span>{t('大小写敏感')}</span>
            {filterType.value === 'include' && (
              <div
                style='margin-left: 14px'
                class='row-control'
              >
                <TCheckbox
                  class='context-filter-checkbox'
                  style='margin-right: 6px'
                  checked={intervalSwitcher.value}
                  onChange={handleChangeIntervalShow}
                />
                <span>{t('显示前')}</span>
                <TInputNumber
                  class='row-control-input'
                  max={100}
                  min={0}
                  placeholder='0'
                  theme='normal'
                  size='small'
                  value={interval.value.prev}
                  onChange={(value: unknown) => {
                    interval.value.prev = Number(value);
                  }}
                />
                <span>{t('行')}</span>
                <span>，</span>
                <span>{t('后')}</span>
                <TInputNumber
                  class='row-control-input'
                  max={100}
                  min={0}
                  placeholder='0'
                  theme='normal'
                  size='small'
                  value={interval.value.next}
                  onChange={(value: unknown) => {
                    interval.value.next = Number(value);
                  }}
                />
                <span>{t('行')}</span>
              </div>
            )}
          </div>
          <div class='operate-right'>
            <div class='color-tip-main'>
              {tipColorList.map((item, index) => (
                <div
                  key={index}
                  class='color-item'
                >
                  <div
                    style={{ background: item.color }}
                    class='rect'
                  ></div>
                  <div>{item.name}</div>
                </div>
              ))}
            </div>
            <TButton class='context-locate-button' theme='default' variant='outline' onClick={() => emit('fix-current-row')}>
              <span
                style='font-size:14px;margin-right:5px'
                class='icon bklog-icon bklog-position'
              ></span>
              <span style='font-size:12px'>{t('定位到当前行')}</span>
            </TButton>
            <div class='log-display-type-main'>
              <div
                class={{
                  'type-item': true,
                  'is-selected': showType.value === 'log',
                }}
                onClick={() => handleSelectShowType('log')}
              >
                {t('日志')}
              </div>
              <div
                class={{
                  'type-item': true,
                  'is-selected': showType.value === 'code',
                }}
                onClick={() => handleSelectShowType('code')}
              >
                {t('代码')}
              </div>
            </div>
            <div
              class='setting-main'
              onClick={handleOpenFieldsConfig}
            >
              <span
                style='font-size: 16px'
                class='icon bklog-icon bklog-set-icon'
              ></span>
            </div>
          </div>
        </div>
        <FieldsConfig
          ref={fieldConfigRef}
          onCancel={() => fieldConfigPopoverInstance?.hide()}
          onSuccess={handleFieldConfigSuccess}
        />
      </div>
    );
  },
});
