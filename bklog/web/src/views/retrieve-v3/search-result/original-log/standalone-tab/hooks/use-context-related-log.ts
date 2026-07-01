import { nextTick, onBeforeUnmount, ref, type Ref } from 'vue';

import $http from '@/api';

import { flattenLogParams, useCommonRelatedLog } from './use-common-related-log';

export const useContextRelatedLog = (options: {
  indexSetId: Ref<number>;
  targetRow: Ref<Record<string, any>>;
  targetFields?: Ref<string[]>;
}) => {
  const common = useCommonRelatedLog(options);
  const zero = ref(true);
  const prevBegin = ref(0);
  const nextBegin = ref(0);
  const error = ref('');

  let requestSeq = 0;
  let scrollTimer: ReturnType<typeof setTimeout> | undefined;
  let bindScrollTimer: ReturnType<typeof setTimeout> | undefined;

  const contentLogRequestId = 'retrieve_getContentLog_contextStandaloneTab';

  const buildBaseData = (direction?: 'top' | 'down') => {
    const params = flattenLogParams(options.targetRow.value);
    const dtEventTimeStamp = params.dtEventTimeStamp ?? options.targetRow.value?.dtEventTimeStamp;
    const data: Record<string, any> = {
      size: 50,
      zero: zero.value,
      dtEventTimeStamp,
      ...params,
    };
    if (direction === 'down') data.begin = nextBegin.value;
    else if (direction === 'top') data.begin = prevBegin.value;
    else data.begin = 0;
    return data;
  };

  const requestContentLog = async (direction?: 'top' | 'down') => {
    requestSeq += 1;
    const currentSeq = requestSeq;
    const dtEventTimeStamp = options.targetRow.value?.dtEventTimeStamp;
    if (!options.indexSetId.value || dtEventTimeStamp === undefined || dtEventTimeStamp === null || dtEventTimeStamp === 'None') {
      return;
    }

    try {
      error.value = '';
      const res = await common.request('retrieve/getContentLog', buildBaseData(direction), contentLogRequestId);
      if (currentSeq !== requestSeq) return;

      const list = res?.data?.list || [];
      if (!list.length) return;

      const formatList = common.formatList(list);
      if (direction === 'down') {
        common.appendRawRows(list);
        nextBegin.value += formatList.length;
      } else if (direction === 'top') {
        common.prependReverseRows(list);
        prevBegin.value -= formatList.length;
      } else {
        const zeroIndex = res.data.zero_index;
        if ((!zeroIndex && zeroIndex !== 0) || zeroIndex === -1) {
          common.logList.value.push({ error: common.t('无法定位上下文') });
          return;
        }
        const normalRows = list.slice(zeroIndex);
        const reverseRows = list.slice(0, zeroIndex);
        common.setRawLists(normalRows, reverseRows);
        const value = zeroIndex - res.data.count_start;
        nextBegin.value = value + normalRows.length;
        prevBegin.value = value - reverseRows.length;
      }

      common.initHighlight(direction);
      if (zero.value) {
        nextTick(scrollToCurrentRowAndBind);
      }
    } catch (e) {
      if (currentSeq === requestSeq) {
        error.value = e?.message || String(e);
        console.warn(e);
      }
    }
  };

  const handleScroll = () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      if (common.loading.value || !common.scrollerRef.value) return;
      const { scrollTop, scrollHeight, offsetHeight } = common.scrollerRef.value;
      if (scrollTop === 0) {
        const beforeHeight = scrollHeight;
        requestContentLog('top').then(() => {
          nextTick(() => {
            if (!common.scrollerRef.value) return;
            common.scrollerRef.value.scrollTo({ top: common.scrollerRef.value.scrollHeight - beforeHeight });
          });
        });
      } else if (scrollHeight - scrollTop - offsetHeight < 1) {
        requestContentLog('down');
      }
    }, 500);
  };

  function scrollToCurrentRowAndBind() {
    common.scrollerRef.value?.removeEventListener('scroll', handleScroll);
    common.scrollToCurrentRow();
    zero.value = false;
    clearTimeout(bindScrollTimer);
    bindScrollTimer = setTimeout(() => {
      common.scrollerRef.value?.addEventListener('scroll', handleScroll, { passive: true });
    });
  }

  const init = async () => {
    common.paramsInfo.value = flattenLogParams(options.targetRow.value);
    common.resetLogs();
    zero.value = true;
    prevBegin.value = 0;
    nextBegin.value = 0;
    await requestContentLog();
  };

  const chooseRow = async (row: Record<string, any>) => {
    options.targetRow.value = row;
    await init();
  };

  const dispose = () => {
    requestSeq += 1;
    clearTimeout(scrollTimer);
    clearTimeout(bindScrollTimer);
    common.scrollerRef.value?.removeEventListener('scroll', handleScroll);
    $http.cancel(contentLogRequestId);
    common.disposeCommon();
  };

  onBeforeUnmount(dispose);

  return {
    ...common,
    error,
    init,
    dispose,
    requestContentLog,
    chooseRow,
    toggleCollapse: () => {},
  };
};
