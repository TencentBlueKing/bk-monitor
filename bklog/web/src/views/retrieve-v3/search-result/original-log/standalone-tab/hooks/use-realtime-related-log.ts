import { nextTick, onBeforeUnmount, ref, type Ref } from 'vue';

import { messageSuccess } from '@/common/bkmagic';

import { flattenLogParams, useCommonRelatedLog } from './use-common-related-log';

export const useRealtimeRelatedLog = (options: {
  indexSetId: Ref<number>;
  targetRow: Ref<Record<string, any>>;
  targetFields?: Ref<string[]>;
}) => {
  const common = useCommonRelatedLog(options);
  const zero = ref(true);
  const isPolling = ref(false);
  const error = ref('');

  const maxLength = Number(window.REAL_TIME_LOG_MAX_LENGTH) || 20000;
  const shiftLength = Number(window.REAL_TIME_LOG_SHIFT_LENGTH) || 10000;

  let timer: ReturnType<typeof setInterval> | undefined;
  let isInit = true;
  let isScrollBottom = true;
  let requestSeq = 0;

  const requestRealTimeLog = async () => {
    if (common.loading.value) return;
    requestSeq += 1;
    const currentSeq = requestSeq;
    const params = flattenLogParams(options.targetRow.value);
    const dtEventTimeStamp = params.dtEventTimeStamp ?? options.targetRow.value?.dtEventTimeStamp;
    if (!options.indexSetId.value || dtEventTimeStamp === undefined || dtEventTimeStamp === null || dtEventTimeStamp === 'None') {
      return;
    }

    try {
      error.value = '';
      const res = await common.request('retrieve/getRealTimeLog', {
        order: '-',
        size: 50,
        zero: zero.value,
        dtEventTimeStamp,
        ...params,
      });
      if (currentSeq !== requestSeq) return;

      const list = res?.data?.list || [];
      if (!list.length) return;

      if (common.logList.value.length > maxLength) {
        common.logList.value.splice(0, shiftLength);
        common.rawList().splice(0, shiftLength);
        common.scrollerRef.value?.scrollTo({ top: 0 });
      }

      if (isInit) {
        common.setRawLists(list.slice(-1), list.slice(0, -1));
            common.paramsInfo.value = flattenLogParams(list[list.length - 1]);
      } else {
        common.appendRawRows(list);
      }

      if (isScrollBottom) {
        nextTick(() => {
          zero.value = false;
          if (!common.scrollerRef.value) return;
          common.scrollerRef.value.scrollTo({
            top: common.scrollerRef.value.scrollHeight - common.scrollerRef.value.offsetHeight,
            behavior: 'smooth',
          });
        });
      }
      common.initHighlight();
    } catch (e) {
      if (currentSeq === requestSeq) {
        error.value = e?.message || String(e);
        console.warn(e);
      }
    } finally {
      isInit = false;
    }
  };

  const togglePoll = (state: boolean) => {
    isPolling.value = state;
    clearInterval(timer);
    if (isPolling.value) {
      timer = setInterval(requestRealTimeLog, 5000);
    }
  };

  const handleScroll = () => {
    if (!common.scrollerRef.value) return;
    const { scrollTop, offsetHeight, scrollHeight } = common.scrollerRef.value;
    isScrollBottom = scrollTop + offsetHeight >= scrollHeight;
  };

  const handleCopy = () => {
    const copyStrList = common.reverseLogList.value.concat(common.logList.value).map(item => item.log);
    const el = document.createElement('textarea');
    el.value = copyStrList.join('\n');
    el.setAttribute('readonly', '');
    el.style.position = 'absolute';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    const selected = document.getSelection()?.rangeCount ? document.getSelection()?.getRangeAt(0) : false;
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    if (selected) {
      document.getSelection()?.removeAllRanges();
      document.getSelection()?.addRange(selected);
    }
    messageSuccess(common.t('复制成功'));
  };

  const init = async () => {
    common.paramsInfo.value = flattenLogParams(options.targetRow.value);
    common.resetLogs();
    zero.value = true;
    isInit = true;
    isScrollBottom = true;
    await requestRealTimeLog();
    togglePoll(true);
    nextTick(() => {
      common.scrollerRef.value?.addEventListener('scroll', handleScroll, { passive: true });
    });
  };

  const chooseRow = async (row: Record<string, any>) => {
    options.targetRow.value = row;
    await init();
  };

  const dispose = () => {
    requestSeq += 1;
    clearInterval(timer);
    common.scrollerRef.value?.removeEventListener('scroll', handleScroll);
    common.disposeCommon();
  };

  onBeforeUnmount(dispose);

  return {
    ...common,
    error,
    maxLength,
    shiftLength,
    isPolling,
    init,
    dispose,
    togglePoll,
    handleCopy,
    chooseRow,
    toggleCollapse: () => {},
  };
};
