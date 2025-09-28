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

import { defineComponent, ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';

import { getFlatObjValues } from '@/common/util';
import FieldsConfig from '@/components/common/fields-config.vue';
import LogView from '@/components/log-view/index.vue';
import useFieldNameHook from '@/hooks/use-field-name';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import CommonHeader from '../components/common-header';
import DataFilter from '../components/data-filter';
import LogResult from '../components/origin-log-result';
import $http from '@/api';

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
    const activeFilterKey = ref('');
    const ignoreCase = ref(false);
    const showType = ref('log');
    const highlightList = ref([]);
    const localParams = ref<any>({});
    const interval = ref({
      prev: 0,
      next: 0,
    });

    let rawList: any[] = [];
    let reverseRawList: any[] = [];
    let firstLogEl: HTMLElement | null = null;
    let throttleTimer: NodeJS.Timeout;
    let timer: NodeJS.Timeout;
    let displayFieldNames: string[] = [];

    watch(
      () => props.isShow,
      () => {
        isShow.value = props.isShow;
        if (isShow.value) {
          setTimeout(() => {
            logResultRef.value.init();
          });
        }
      },
      {
        immediate: true,
      },
    );

    watch(
      () => [props.indexSetId, props.logParams],
      async () => {
        if (props.indexSetId && props.logParams) {
          deepClone(props.logParams);
          await requestContentLog();
        }
      },
      {
        immediate: true,
      },
    );

    const initLogValues = () => {
      logLoading.value = false;
      logList.value = [];
      rawList = [];
      reverseLogList.value = [];
      reverseRawList = [];
      nextBegin.value = 0;
      prevBegin.value = 0;
      zero.value = true;
    };

    const handleAfterLeave = () => {
      dataFilterRef.value.reset();
      logResultRef.value.reset();
      highlightList.value = [];
      interval.value = {
        prev: 0,
        next: 0,
      };
      ignoreCase.value = false;
      activeFilterKey.value = '';
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
      if (event.keyCode === 27) {
        emit('close-dialog');
      }
    };

    const deepClone = (obj, prefix = '') => {
      for (const key in obj) {
        const prefixKey = prefix ? `${prefix}.${key}` : key;
        if (typeof obj[key] === 'object') {
          deepClone(obj[key], prefixKey);
        } else {
          localParams.value[prefixKey] = String(obj[key])
            .replace(/<mark>/g, '')
            .replace(/<\/mark>/g, '');
        }
      }
    };

    const requestContentLog = async (direction?: string) => {
      const data: any = Object.assign(
        {
          size: 50,
          zero: zero.value,
          dtEventTimeStamp: props.logParams.dtEventTimeStamp,
        },
        localParams.value,
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
        });

        const { list } = res.data;
        if (list?.length > 0) {
          const formatList = hadnleFormatList(list, displayFieldNames.length ? displayFieldNames : ['log']);
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
        console.error(e);
      } finally {
        logLoading.value = false;
        if (highlightList.value.length) {
          setTimeout(() => {
            dataFilterRef.value.getHighlightControl()?.initLightItemList(direction);
          });
        }
        if (zero.value) {
          nextTick(() => {
            initLogScrollPosition();
          });
        }
      }
    };

    /**
     * 将列表根据字段组合成字符串数组
     **/
    const hadnleFormatList = (list, displayFieldNames) => {
      const filterDisplayList: any[] = [];
      list.forEach(listItem => {
        const displayObj = {};
        const { newObject } = getFlatObjValues(listItem);
        const { changeFieldName } = useFieldNameHook({ store });
        displayFieldNames.forEach(field => {
          Object.assign(displayObj, {
            [field]: newObject[changeFieldName(field)],
          });
        });
        filterDisplayList.push(displayObj);
      });
      return filterDisplayList;
    };

    // 确定设置显示字段
    const handleConfirmFieldsConfig = async (list: string[]) => {
      displayFieldNames = list;
      logList.value = hadnleFormatList(rawList, list);
      reverseLogList.value = hadnleFormatList(reverseRawList, list);
    };

    const initLogScrollPosition = () => {
      // 确定第0条的位置
      firstLogEl = document.querySelector('.dialog-log-markdown .log-init');
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
      setTimeout(() => {
        contextLog.value.addEventListener('scroll', handleScroll, {
          passive: true,
        });
      });
    };

    const handleScroll = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (logLoading.value) {
          return;
        }

        const { scrollTop, scrollHeight, offsetHeight } = contextLog.value;
        if (scrollTop === 0) {
          // 滚动到顶部
          requestContentLog('top').then(() => {
            nextTick(() => {
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

    const filterLog = value => {
      activeFilterKey.value = value;
      clearTimeout(throttleTimer);
      throttleTimer = setTimeout(() => {
        if (!value) {
          nextTick(() => {
            initLogScrollPosition();
          });
        }
      }, 300);
    };

    const handleChooseRow = (data: Record<string, string>) => {
      initLogValues();
      deepClone(data);
      requestContentLog();
    };

    onMounted(() => {
      document.addEventListener('keyup', handleKeyup);
      nextTick(() => {
        (document.querySelector('.dialog-log-markdown') as HTMLElement).focus();
      });
    });

    onBeforeUnmount(() => {
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
          initial-divide={250}
          placement='bottom'
          auto-minimize
          collapsible
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
                v-bkloading={{ isLoading: logLoading.value, opacity: 0.6 }}
              >
                {logList.value.length > 0 ? (
                  <LogView
                    filter-key={activeFilterKey.value}
                    filter-type={filterType.value}
                    ignore-case={ignoreCase.value}
                    interval={interval.value}
                    light-list={highlightList.value}
                    log-list={logList.value}
                    reverse-log-list={reverseLogList.value}
                    show-type={showType.value}
                  />
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
            />
          )}
        </bk-resize-layout>
      </bk-dialog>
    );
  },
});
