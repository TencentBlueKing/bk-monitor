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
import { computed, defineComponent, ref, watch, nextTick } from 'vue';

import { deepClone, contextHighlightColor } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import { cloneDeep } from 'lodash';
import tippy from 'tippy.js';

import FieldsConfig from './fields-config';
import HighlightControl from './highlight-control';

import './index.scss';

export default defineComponent({
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
    const tagInputRef = ref<any>(null);
    const filterType = ref('include');
    const filterKey = ref('');
    const catchFilterKey = ref('');
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
      catchFilterKey.value = filterKey.value;
      emit('handle-filter', 'filterKey', filterKey.value);
    };
    const blurFilterLog = () => {
      if (!catchFilterKey.value && !filterKey.value) return;
      filterLog();
    };

    const changeLightList = () => {
      // 找出未显示的颜色
      const colorIndex = contextHighlightColor.findIndex((item, index) => !catchColorIndexList.value.includes(index));
      const catchCloneColorList = deepClone(colorHighlightList.value);
      // 给高亮颜色重新赋值
      colorHighlightList.value = highlightList.value.map(item => {
        const notChangeItem = catchCloneColorList.find(cItem => cItem.heightKey === item);
        if (notChangeItem) return notChangeItem;
        return {
          heightKey: item,
          colorIndex,
          color: contextHighlightColor[colorIndex],
        };
      });
      // 更新input输入框的颜色
      nextTick(() => {
        initTagInputColor();
      });
      emit('handle-filter', 'highlightList', colorHighlightList.value);
    };
    const handleFilterType = (val: string) => {
      filterType.value = val;
      emit('handle-filter', 'filterType', val);
    };
    const handleSelectShowType = type => {
      showType.value = type;
      emit('handle-filter', 'showType', type);
    };
    const handleChangeIntervalShow = (state: boolean) => {
      intervalSwitcher.value = state;
      emit('handle-filter', 'interval', state ? interval.value : baseInterval);
    };
    // 粘贴过滤条件
    const pasteFn = (pasteValue: string) => {
      const trimPasteValue = pasteValue.trim();
      if (!highlightList.value.includes(trimPasteValue) && highlightList.value.length < 5) {
        highlightList.value.push(trimPasteValue);
        changeLightList();
      }
      return [];
    };
    /** 更新taginput组件中的颜色 */
    const initTagInputColor = () => {
      const childEl = tagInputRef.value.$el.querySelectorAll('.key-node');
      childEl.forEach(child => {
        const tag = child.querySelectorAll('.tag')[0];
        const colorObj = colorHighlightList.value.find(item => item.heightKey === tag.innerText);
        [child, tag].forEach(item => {
          Object.assign(item.style, {
            backgroundColor: colorObj.color.light,
          });
        });
      });
    };

    const handleOpenFieldsConfig = (e: any) => {
      if (!fieldConfigPopoverInstance) {
        fieldConfigPopoverInstance = tippy(e.target, {
          allowHTML: true,
          appendTo: () => document.body,
          content: fieldConfigRef.value.getDom(),
          placement: 'bottom',
          trigger: 'click',
          maxWidth: 380,
          theme: 'light field-config-popover',
          hideOnClick: false,
          interactive: true,
          arrow: true,
        });
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
        interval.value = cloneDeep(baseInterval);
        ignoreCase.value = false;
        filterKey.value = '';
        showType.value = 'log';
        filterType.value = 'include';
        fieldConfigPopoverInstance?.hide();
      },
      getHighlightControl: () => highlightControlRef.value,
    });

    return () => (
      <div class='filter-bar-main'>
        <div class='filter-item-top'>
          <div class='filter-main'>
            <bk-select
              class='filter-select-main'
              clearable={false}
              value={filterType.value}
              on-change={handleFilterType}
            >
              {filterTypeList.map((option, index) => (
                <bk-option
                  id={option.id}
                  key={index}
                  name={option.name}
                />
              ))}
            </bk-select>
            <bk-input
              class='filter-key-input'
              placeholder={t('输入关键字进行过滤')}
              right-icon='bk-icon icon-search'
              value={filterKey.value}
              clearable
              on-blur={blurFilterLog}
              on-change={value => {
                filterKey.value = value;
              }}
              on-clear={filterLog}
              on-enter={filterLog}
            />
          </div>
          <div class='highlight-main'>
            <div class='prefix-text'>{t('label-高亮').replace('label-', '')}</div>
            <bk-tag-input
              ref={tagInputRef}
              class='highlight-tag-input'
              max-data={5}
              paste-fn={pasteFn}
              value={highlightList.value}
              allow-create
              has-delete-icon
              on-change={value => {
                highlightList.value = value;
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
                on-click={handleTogglePolling}
              >
                {isPolling.value ? <log-icon type='zanting' /> : <log-icon type='bofang' />}
              </div>
              <div
                class='control-item'
                on-click={() => emit('copy')}
              >
                <log-icon type='copy' />
              </div>
            </div>
          )}
        </div>
        <div class='filter-item-bottom'>
          <div class='operate-left'>
            <bk-checkbox
              style='margin-right: 6px'
              value={ignoreCase.value}
              on-change={value => {
                ignoreCase.value = value;
              }}
            />
            <span>{t('大小写敏感')}</span>
            {filterType.value === 'include' && (
              <div
                style='margin-left: 14px'
                class='row-control'
              >
                <bk-checkbox
                  style='margin-right: 6px'
                  value={intervalSwitcher.value}
                  on-change={handleChangeIntervalShow}
                />
                <span>{t('显示前')}</span>
                <bk-input
                  class='row-control-input'
                  max={100}
                  min={0}
                  placeholder='0'
                  show-controls={false}
                  size='small'
                  type='number'
                  value={interval.value.prev}
                  on-change={value => {
                    interval.value.prev = Number(value);
                  }}
                />
                <span>{t('行')}</span>
                <span>，</span>
                <span>{t('后')}</span>
                <bk-input
                  class='row-control-input'
                  max={100}
                  min={0}
                  placeholder='0'
                  show-controls={false}
                  size='small'
                  type='number'
                  value={interval.value.next}
                  on-change={value => {
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
            <bk-button on-click={() => emit('fix-current-row')}>
              <span
                style='font-size:14px;margin-right:5px'
                class='icon bklog-icon bklog-position'
              ></span>
              <span style='font-size:12px'>{t('定位到当前行')}</span>
            </bk-button>
            <div class='log-display-type-main'>
              <div
                class={{
                  'type-item': true,
                  'is-selected': showType.value === 'log',
                }}
                on-click={() => handleSelectShowType('log')}
              >
                {t('日志')}
              </div>
              <div
                class={{
                  'type-item': true,
                  'is-selected': showType.value === 'code',
                }}
                on-click={() => handleSelectShowType('code')}
              >
                {t('代码')}
              </div>
            </div>
            {!props.isRealTime && (
              <div
                class='setting-main'
                on-click={handleOpenFieldsConfig}
              >
                <span
                  style='font-size: 16px'
                  class='icon bklog-icon bklog-set-icon'
                ></span>
              </div>
            )}
          </div>
        </div>
        <FieldsConfig
          ref={fieldConfigRef}
          on-cancel={() => fieldConfigPopoverInstance?.hide()}
          on-success={handleFieldConfigSuccess}
        />
      </div>
    );
  },
});
