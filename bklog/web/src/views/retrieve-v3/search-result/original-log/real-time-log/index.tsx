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

import { messageSuccess } from '@/common/bkmagic';
import { getFlatObjValues } from '@/common/util';
import FieldsConfig from '@/components/common/fields-config.vue';
import LogView from '@/components/log-view/index.vue';
import useLocale from '@/hooks/use-locale';

import CommonHeader from '../components/common-header';
import DataFilter from '../components/data-filter';
import LogResult from '../components/origin-log-result';
import $http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'RealTimeLog',
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
    const { t } = useLocale();

    const dataFilterRef = ref();
    const logResultRef = ref();
    const contextLog = ref();
    const isShow = ref(false);
    const logLoading = ref(false);
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
    const rowShowParams = ref<any>({});
    const interval = ref({
      prev: 0,
      next: 0,
    });

    // 日志最大长度
    const maxLength = Number(window.REAL_TIME_LOG_MAX_LENGTH) || 20000;
    // 超过此长度删除部分日志
    const shiftLength = Number(window.REAL_TIME_LOG_SHIFT_LENGTH) || 10000;

    let firstLogEl: HTMLElement | null = null;
    let throttleTimer: NodeJS.Timeout;
    let timer: NodeJS.Timeout;
    let isPolling = false;
    let isInit = true;
    let isScrollBottom = true;

    watch(
      () => props.isShow,
      () => {
        isShow.value = props.isShow;
        if (isShow.value) {
          setTimeout(() => {
            logResultRef.value.init();
          });
        } else {
          clearInterval(timer);
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
          requestRealTimeLog();
          handleTogglePoll(true);
        }
      },
      {
        immediate: true,
      },
    );

    const initLogValues = () => {
      logLoading.value = false;
      logList.value = [];
      reverseLogList.value = [];
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

    const deepClone = (obj: any) => {
      const string = JSON.stringify(obj)
        .replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');
      // 扁平化对象内的对象值
      const parseObj = JSON.parse(string);
      if (props.targetFields.length) {
        const { newObject } = getFlatObjValues(parseObj);
        rowShowParams.value = newObject;
      }
      localParams.value = parseObj;
    };

    const easeScroll = (to = 0, duration = 300, target: any) => {
      const start = target === window ? target.scrollY : target.scrollTop;
      const beginTime = Date.now();

      requestAnimationFrame(animate);

      function animate() {
        const nowTime = Date.now();
        const time = nowTime - beginTime;
        target.scrollTo({
          top: computeCoordinate(time, start, to, duration),
        });
        if (time < duration) {
          requestAnimationFrame(animate);
        }
      }

      function computeCoordinate(time, start, to, duration) {
        // 计算滚动绝对纵坐标
        let factor = (time / duration) ** 2; // 系数为 1 就是 linear 效果
        if (factor > 1) factor = 1;
        return start + (to - start) * factor;
      }
    };

    const requestRealTimeLog = () => {
      if (logLoading.value || !isShow.value) {
        return false;
      }
      logLoading.value = true;
      $http
        .request('retrieve/getRealTimeLog', {
          params: {
            index_set_id: props.indexSetId,
          },
          data: Object.assign(
            {
              order: '-',
              size: 50,
              zero: zero.value,
              dtEventTimeStamp: props.logParams.dtEventTimeStamp,
            },
            localParams.value,
          ),
        })
        .then(res => {
          // 通过gseindex 去掉出返回日志， 并加入现有日志
          const { list } = res.data;
          if (list?.length) {
            // 超过最大长度时剔除部分日志
            if (logList.value.length > maxLength) {
              logList.value.splice(0, shiftLength);
              contextLog.value.scrollTo({ top: 0 });
            }

            const logArr: any[] = [];
            list.forEach(item => {
              const { log } = item;
              logArr.push({ log });
            });
            deepClone(list[list.length - 1]);
            if (isInit) {
              reverseLogList.value = logArr.slice(0, -1);
              logList.value = logArr.slice(-1);
            } else {
              logList.value.splice(logList.value.length, 0, ...logArr);
            }
            if (isScrollBottom) {
              nextTick(() => {
                if (zero.value) {
                  zero.value = false;
                }
                easeScroll(contextLog.value.scrollHeight - contextLog.value.offsetHeight, 300, contextLog.value);
              });
            }
          }
        })
        .finally(() => {
          isInit = false;
          logLoading.value = false;
          if (highlightList.value.length) {
            setTimeout(() => {
              dataFilterRef.value.getHighlightControl()?.initLightItemList();
            });
          }
        });
    };

    const initLogScrollPosition = () => {
      // 确定第0条的位置
      firstLogEl = document.querySelector('.dialog-log-markdown .log-init');
      // 没有数据
      if (!firstLogEl) return;
      const logContentHeight = firstLogEl.scrollHeight;
      const logOffsetTop = firstLogEl.offsetTop;

      const wrapperOffsetHeight = contextLog.value.offsetHeight;

      if (wrapperOffsetHeight <= logContentHeight) {
        contextLog.value.scrollTop = logOffsetTop;
      } else {
        contextLog.value.scrollTop = logOffsetTop - Math.ceil((wrapperOffsetHeight - logContentHeight) / 2);
      }
      zero.value = false;
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

    const filterLog = (value: string) => {
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
      requestRealTimeLog();
    };

    const handleTogglePoll = (isPoll: boolean) => {
      isPolling = isPoll;
      clearInterval(timer);
      if (isPolling) {
        timer = setInterval(requestRealTimeLog, 5000);
      }
    };

    const handleCopy = () => {
      const el = document.createElement('textarea');
      const copyStrList = reverseLogList.value.concat(logList.value).map(item => item.log);
      el.value = copyStrList.join('\n');
      el.setAttribute('readonly', '');
      el.style.position = 'absolute';
      el.style.left = '-9999px';
      document.body.appendChild(el);
      const selected = document.getSelection().rangeCount > 0 ? document.getSelection().getRangeAt(0) : false;
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      if (selected) {
        document.getSelection().removeAllRanges();
        document.getSelection().addRange(selected);
      }
      messageSuccess(t('复制成功'));
    };

    const handleScroll = () => {
      const { scrollTop, offsetHeight } = contextLog.value;
      const contentHeight = contextLog.value.scrollHeight;
      if (scrollTop + offsetHeight >= contentHeight) {
        isScrollBottom = true;
      } else {
        isScrollBottom = false;
      }
    };

    onMounted(() => {
      initLogScrollPosition();
      contextLog.value.addEventListener('scroll', handleScroll);
      document.addEventListener('keyup', handleKeyup);
    });

    onBeforeUnmount(() => {
      document.removeEventListener('keyup', handleKeyup);
      contextLog.value.removeEventListener('scroll', handleScroll);
      clearInterval(timer);
    });

    return () => (
      <bk-dialog
        ext-cls='log-realtime-dialog-main'
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
                  isRealTime
                  on-copy={handleCopy}
                  on-fix-current-row={handleFixCurrentRow}
                  on-handle-filter={handleFilter}
                  on-toggle-poll={handleTogglePoll}
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
                    max-length={maxLength}
                    reverse-log-list={reverseLogList.value}
                    shift-length={shiftLength}
                    show-type={showType.value}
                    isRealTimeLog
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
