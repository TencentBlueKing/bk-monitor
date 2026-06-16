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

import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { getFlatObjValues } from '@/common/util';
import FieldsConfig from '@/components/common/fields-config.vue';
import LogView from '@/components/log-view/index.vue';
import useFieldNameHook from '@/hooks/use-field-name';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import $http from '@/api';
import { getDefaultDisplayFields } from '../components/data-filter/fields-config/default-display-fields';
import CommonHeader from '../components/common-header';
import DataFilter from '../components/data-filter';
import LogResult from '../components/origin-log-result';

import './index.scss';

export default defineComponent({
  name: 'ContextLog',
  components: {
    LogView,
    FieldsConfig,
    DataFilter,
    LogResult,
    CommonHeader,
  },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    retrieveParams: {
      type: Object,
      required: true,
    },
    logParams: {
      type: Object,
      default: () => ({}),
    },
    targetFields: {
      type: Array,
      default: () => [],
    },
    indexSetId: {
      type: Number,
      default: 0,
    },
    rowIndex: {
      type: Number,
      default: 0,
    },
  },
  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale();

    const logViewRef = ref();
    const dataFilterRef = ref();
    const logResultRef = ref();
    const contextLog = ref();
    const isShow = ref(false);
    const logLoading = ref(false); // 展示的字段名
    const logList = ref<any[]>([]);
    const reverseLogList = ref<any[]>([]);
    const zero = ref(true);
    const prevBegin = ref(0);
    const nextBegin = ref(0);
    const filterType = ref('include');
    const activeFilterKey = ref<string[]>([]);
    const ignoreCase = ref(false);
    const showType = ref('log');
    const highlightList = ref([]);
    const localParams = ref<any>({});
    const initialDivide = ref(250);
    const isFilterEmpty = ref(false);
    const interval = ref({
      prev: 0,
      next: 0,
    });

    let rawList: any[] = [];
    let reverseRawList: any[] = [];
    let firstLogEl: HTMLElement | null = null;
    let throttleTimer: ReturnType<typeof setTimeout>;
    let timer: ReturnType<typeof setTimeout>;
    let scrollBindTimer: ReturnType<typeof setTimeout>;
    let highlightTimer: ReturnType<typeof setTimeout>;
    let initLogResultTimer: ReturnType<typeof setTimeout>;
    let filterCheckTimer: ReturnType<typeof setTimeout>;
    let handleScroll = () => {};
    let displayFieldNames: string[] = [];
    let contextLogRequestSeq = 0;

    const contentLogRequestId = 'retrieve_getContentLog_contextLog';
    const isContextLogVisible = () => isShow.value && props.isShow;
    const isCurrentContextLogRequest = (requestSeq: number) => isContextLogVisible() && requestSeq === contextLogRequestSeq;

    const clearContextLogTimers = () => {
      clearTimeout(timer);
      clearTimeout(throttleTimer);
      clearTimeout(scrollBindTimer);
      clearTimeout(highlightTimer);
      clearTimeout(initLogResultTimer);
      clearTimeout(filterCheckTimer);
    };

    const cleanupContextLogEffects = () => {
      contextLogRequestSeq += 1;
      clearContextLogTimers();
      contextLog.value?.removeEventListener('scroll', handleScroll);
      logLoading.value = false;
      $http.cancel(contentLogRequestId);
    };

    watch(
      () => props.isShow,
      () => {
        isShow.value = props.isShow;
        if (isShow.value) {
          contextLogRequestSeq += 1;
          initLogResultTimer = setTimeout(() => {
            if (isContextLogVisible()) {
              logResultRef.value?.init();
            }
          });
          return;
        }

        cleanupContextLogEffects();
      },
      {
        immediate: true,
      },
    );

    watch(
      () => [props.indexSetId, props.logParams],
      async () => {
        if (isContextLogVisible() && props.indexSetId && props.logParams && Object.keys(props.logParams).length) {
          localParams.value = {};
          deepClone(props.logParams);
          await requestContentLog();
        }
      },
      {
        immediate: true,
      },
    );

    watch(activeFilterKey, () => {
      clearTimeout(filterCheckTimer);
      filterCheckTimer = setTimeout(() => {
        if (!isContextLogVisible()) {
          return;
        }

        const lineDomList = Array.from(logViewRef.value?.$el.querySelectorAll('.line') || []);
        if (lineDomList.length && lineDomList.every((item: any) => item.style.display === 'none')) {
          isFilterEmpty.value = true;
          return;
        }
        isFilterEmpty.value = false;
      });
    });

    const initLogValues = () => {
      logLoading.value = false;
      logList.value = [];
      rawList = [];
      reverseLogList.value = [];
      reverseRawList = [];
      nextBegin.value = 0;
      prevBegin.value = 0;
      zero.value = true;
      localParams.value = {};
    };

    const handleAfterLeave = () => {
      cleanupContextLogEffects();
      dataFilterRef.value?.reset();
      logResultRef.value?.reset();
      highlightList.value = [];
      interval.value = {
        prev: 0,
        next: 0,
      };
      ignoreCase.value = false;
      activeFilterKey.value = [];
      showType.value = 'log';
      filterType.value = 'include';
      initLogValues();
      emit('close-dialog');
    };

    const handleFixCurrentRow = () => {
      const listElement = contextLog.value.querySelector('#log-content');
      const activeRow = listElement.querySelector('.line.log-init');
      const scrollTop = activeRow.offsetTop;
      contextLog.value.scrollTo({
        left: 0,
        top: scrollTop,
        behavior: 'smooth',
      });
    };

    const handleKeyup = (event: any) => {
      if (event.keyCode === 27 && isContextLogVisible()) {
        cleanupContextLogEffects();
        handleAfterLeave();
      }
    };

    const deepClone = (obj, prefix = '') => {
      for (const key in obj) {
        const prefixKey = prefix ? `${prefix}.${key}` : key;
        if (typeof obj[key] === 'object') {
          if (obj[key]?._isBigNumber) {
            localParams.value[prefixKey] = obj[key].toString();
          } else {
            deepClone(obj[key], prefixKey);
          }
        } else {
          localParams.value[prefixKey] = String(obj[key])
            .replace(/<mark>/g, '')
            .replace(/<\/mark>/g, '');
        }
      }
    };

    /**
     * 获取上下文显示字段。
     * 只从字段列表中选择：用户配置 -> log -> 第一个 text 字段 -> 第一个字段。
     */
    const getShowFieldNames = () => displayFieldNames.length
      ? displayFieldNames
      : getDefaultDisplayFields(store, store.state.retrieve.catchFieldCustomConfig?.contextDisplayFields);

    const normalizeDisplayValue = (value: any) => {
      if (value === null || value === undefined) {
        return ' ';
      }
      if (typeof value === 'object') {
        try {
          return JSON.stringify(value);
        } catch (e) {
          return String(value);
        }
      }
      return value;
    };

    const getDisplayFieldValue = (row: Record<string, any>, flatRow: Record<string, any>, field: string) => {
      const { changeFieldName } = useFieldNameHook({ store });
      const realField = changeFieldName(field);
      const value = flatRow[realField] ?? row[realField] ?? row[field] ?? flatRow[field];
      return normalizeDisplayValue(value);
    };

    const requestContentLog = async (direction?: string) => {
      if (!isContextLogVisible()) {
        return;
      }

      const requestSeq = contextLogRequestSeq;
      const paramsSnapshot = { ...localParams.value };
      const dtEventTimeStamp = paramsSnapshot.dtEventTimeStamp ?? props.logParams?.dtEventTimeStamp;
      if (!props.indexSetId || dtEventTimeStamp === undefined || dtEventTimeStamp === null || dtEventTimeStamp === 'None') {
        return;
      }

      const data: any = Object.assign(
        {
          size: 50,
          zero: zero.value,
          dtEventTimeStamp,
        },
        paramsSnapshot,
      );
      if (direction === 'down') {
        data.begin = nextBegin.value;
      } else if (direction === 'top') {
        data.begin = prevBegin.value;
      } else {
        data.begin = 0;
      }

      try {
        logLoading.value = true;
        const res = await $http.request('retrieve/getContentLog', {
          params: {
            index_set_id: props.indexSetId,
          },
          data,
        }, {
          catchIsShowMessage: false,
          requestId: contentLogRequestId,
        });

        if (!isCurrentContextLogRequest(requestSeq)) {
          return;
        }

        const { list } = res.data;
        if (list?.length > 0) {
          const formatList = handleFormatList(list, getShowFieldNames());
          if (direction) {
            if (direction === 'down') {
              logList.value.push(...formatList);
              rawList.push(...list);
              nextBegin.value += formatList.length;
            } else {
              reverseLogList.value.unshift(...formatList);
              reverseRawList.unshift(...list);
              prevBegin.value -= formatList.length;
            }
          } else {
            const zeroIndex = res.data.zero_index;
            if ((!zeroIndex && zeroIndex !== 0) || zeroIndex === -1) {
              logList.value.splice(logList.value.length, 0, {
                error: t('无法定位上下文'),
              });
            } else {
              logList.value.push(...formatList.slice(zeroIndex, list.length));
              rawList.push(...list.slice(zeroIndex, list.length));
              reverseLogList.value.unshift(...formatList.slice(0, zeroIndex));
              reverseRawList.unshift(...list.slice(0, zeroIndex));
              const value = zeroIndex - res.data.count_start;
              nextBegin.value = value + logList.value.length;
              prevBegin.value = value - reverseLogList.value.length;
            }
          }
        }
      } catch (e) {
        if (isCurrentContextLogRequest(requestSeq)) {
          console.warn(e);
        }
      } finally {
        if (isCurrentContextLogRequest(requestSeq)) {
          logLoading.value = false;
          if (highlightList.value.length) {
            highlightTimer = setTimeout(() => {
              if (isCurrentContextLogRequest(requestSeq)) {
                dataFilterRef.value?.getHighlightControl()?.initLightItemList(direction);
              }
            });
          }
          if (zero.value) {
            nextTick(() => {
              if (isCurrentContextLogRequest(requestSeq)) {
                initLogScrollPosition();
              }
            });
          }
        }
      }
    };

    /**
     * 将列表根据字段组合成字符串数组
     **/
    const handleFormatList = (list, displayFieldNames) => {
      const filterDisplayList: any[] = [];
      list.forEach((listItem) => {
        const displayObj = {};
        const { newObject } = getFlatObjValues(listItem);
        displayFieldNames.forEach((field) => {
          Object.assign(displayObj, {
            [field]: getDisplayFieldValue(listItem, newObject, field),
          });
        });
        filterDisplayList.push(displayObj);
      });
      return filterDisplayList;
    };

    // 确定设置显示字段
    const handleConfirmFieldsConfig = async (list: string[]) => {
      displayFieldNames = list;
      logList.value = handleFormatList(rawList, list);
      reverseLogList.value = handleFormatList(reverseRawList, list);
    };

    const initLogScrollPosition = () => {
      if (!isContextLogVisible() || !contextLog.value) {
        return;
      }

      // 确定第0条的位置
      firstLogEl = contextLog.value.querySelector('.log-init');
      // 没有数据
      if (!firstLogEl) return;
      contextLog.value.removeEventListener('scroll', handleScroll);
      const logContentHeight = firstLogEl.scrollHeight;
      const logOffsetTop = firstLogEl.offsetTop;

      const wrapperOffsetHeight = contextLog.value.offsetHeight;

      if (wrapperOffsetHeight <= logContentHeight) {
        contextLog.value.scrollTop = logOffsetTop;
      } else {
        contextLog.value.scrollTop = logOffsetTop - Math.ceil((wrapperOffsetHeight - logContentHeight) / 2);
      }
      zero.value = false;

      // 避免重复请求
      clearTimeout(scrollBindTimer);
      scrollBindTimer = setTimeout(() => {
        if (isContextLogVisible() && contextLog.value) {
          contextLog.value.addEventListener('scroll', handleScroll, {
            passive: true,
          });
        }
      });
    };

    handleScroll = () => {
      if (!isContextLogVisible()) {
        return;
      }

      clearTimeout(timer);
      const requestSeq = contextLogRequestSeq;
      timer = setTimeout(() => {
        if (!isCurrentContextLogRequest(requestSeq) || logLoading.value || !contextLog.value) {
          return;
        }

        const { scrollTop, scrollHeight, offsetHeight } = contextLog.value;
        if (scrollTop === 0) {
          // 滚动到顶部
          requestContentLog('top').then(() => {
            nextTick(() => {
              if (!isCurrentContextLogRequest(requestSeq) || !contextLog.value) {
                return;
              }

              // 记录刷新前滚动位置
              const newScrollHeight = contextLog.value.scrollHeight;
              contextLog.value.scrollTo({
                top: newScrollHeight - scrollHeight,
              });
            });
          });
        } else if (scrollHeight - scrollTop - offsetHeight < 1) {
          // 滚动到底部
          requestContentLog('down');
        }
      }, 1000);
    };

    const handleFilter = (field: string, value: any) => {
      switch (field) {
        case 'filterKey':
          filterLog(value);
          break;
        case 'showType':
          showType.value = value;
          break;
        case 'ignoreCase':
          ignoreCase.value = value;
          break;
        case 'interval':
          interval.value = value;
          break;
        case 'filterType':
          filterType.value = value;
          break;
        default:
          highlightList.value = value;
      }
    };

    const filterLog = (value) => {
      activeFilterKey.value = value;
      clearTimeout(throttleTimer);
      throttleTimer = setTimeout(() => {
        if (!value.length) {
          nextTick(() => {
            initLogScrollPosition();
          });
        }
      }, 300);
    };

    const handleChooseRow = (data: Record<string, string>) => {
      cleanupContextLogEffects();
      contextLogRequestSeq += 1;
      initLogValues();
      deepClone(data);
      requestContentLog();
    };

    const handleToggleCollapse = (isCollapsed: boolean) => {
      const minHeight = window.__IS_MONITOR_APM__ ? 20 : 42;
      initialDivide.value = isCollapsed ? minHeight : 250;
    };

    onMounted(() => {
      document.addEventListener('keyup', handleKeyup);
      nextTick(() => {
        (document.querySelector('.dialog-log-markdown') as HTMLElement).focus();
      });
    });

    onBeforeUnmount(() => {
      cleanupContextLogEffects();
      document.removeEventListener('keyup', handleKeyup);
    });

    return () => (
      <bk-dialog
        ext-cls='log-context-dialog-main'
        draggable={false}
        esc-close={false}
        mask-close={false}
        render-directives='if'
        show-footer={false}
        value={isShow.value}
        fullscreen
        on-after-leave={handleAfterLeave}
      >
        <bk-resize-layout
          style='height: 100%'
          border={false}
          initial-divide={initialDivide.value}
          min={42}
          placement='bottom'
        >
          <div
            class='context-log-wrapper'
            slot='main'
          >
            <CommonHeader
              paramsInfo={localParams.value}
              targetFields={props.targetFields}
            />
            <div class='context-main'>
              <div class='data-filter-wraper'>
                <DataFilter
                  ref={dataFilterRef}
                  on-fields-config-update={handleConfirmFieldsConfig}
                  on-fix-current-row={handleFixCurrentRow}
                  on-handle-filter={handleFilter}
                />
              </div>
              <div
                ref={contextLog}
                class='dialog-log-markdown'
                v-bkloading={{
                  isLoading: logLoading.value && !isFilterEmpty.value,
                  opacity: 0.6,
                }}
              >
                {logList.value.length > 0 ? (
                  isFilterEmpty.value ? (
                    <bk-exception
                      style='margin-top: 80px'
                      scene='part'
                      type='search-empty'
                    >
                      <span>{t('搜索结果为空')}</span>
                    </bk-exception>
                  ) : (
                    <LogView
                      ref={logViewRef}
                      filter-key={activeFilterKey.value}
                      filter-type={filterType.value}
                      ignore-case={ignoreCase.value}
                      interval={interval.value}
                      light-list={highlightList.value}
                      log-list={logList.value}
                      reverse-log-list={reverseLogList.value}
                      show-type={showType.value}
                    />
                  )
                ) : !logLoading.value ? (
                  <bk-exception
                    style='margin-top: 80px'
                    scene='part'
                    type='empty'
                  >
                    <span>{t('暂无数据')}</span>
                  </bk-exception>
                ) : null}
              </div>
            </div>
          </div>
          {isShow.value && (
            <LogResult
              ref={logResultRef}
              slot='aside'
              indexSetId={props.indexSetId}
              logIndex={props.rowIndex}
              retrieveParams={props.retrieveParams}
              on-choose-row={handleChooseRow}
              on-toggle-collapse={handleToggleCollapse}
            />
          )}
        </bk-resize-layout>
      </bk-dialog>
    );
  },
});
