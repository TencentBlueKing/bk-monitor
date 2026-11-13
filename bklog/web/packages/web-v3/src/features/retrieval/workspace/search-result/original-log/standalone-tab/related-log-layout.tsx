import { renderLogListSkeleton, renderListRefreshSkeleton } from '@/shared/ui/loading/list-skeleton';
import { defineComponent, nextTick, onMounted, ref, type PropType } from 'vue';

import LogView from '@/features/retrieval/log-view/index.vue';

import CommonHeader from '../components/common-header/index';
import DataFilter from '../components/data-filter/index';
import LogResult from '../components/origin-log-result/index';

export interface RelatedLogViewModel {
  t: (_key: string) => string;
  logViewRef: any;
  dataFilterRef: any;
  scrollerRef: any;
  loading: any;
  error: any;
  logList: any;
  reverseLogList: any;
  filterType: any;
  activeFilterKey: any;
  ignoreCase: any;
  showType: any;
  highlightList: any;
  interval: any;
  isFilterEmpty: any;
  paramsInfo: any;
  targetFields: any;
  handleFieldsConfigUpdate: (_fields: string[]) => void;
  handleFilter: (_field: string, _value: any) => void;
  scrollToCurrentRow: () => void;
  isPolling?: any;
  togglePoll?: (_state: boolean) => void;
  handleCopy?: () => void;
  maxLength?: number;
  shiftLength?: number;
  indexSetId?: any;
  rowIndex?: any;
  retrieveParams?: any;
  chooseRow?: (_row: Record<string, any>) => void;
  toggleCollapse?: (_state: boolean) => void;
}

export default defineComponent({
  name: 'RelatedLogLayout',
  props: {
    title: {
      type: String,
      required: true,
    },
    viewModel: {
      type: Object as PropType<RelatedLogViewModel>,
      required: true,
    },
    isRealTime: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const logResultRef = ref<any>();
    const collapsedDivide = window.__IS_MONITOR_APM__ ? 20 : 42;
    const initialDivide = ref(250);

    onMounted(() => {
      nextTick(() => {
        logResultRef.value?.init?.();
      });
    });

    const noop = () => {};
    const handleToggleCollapse = (isCollapsed: boolean) => {
      initialDivide.value = isCollapsed ? collapsedDivide : 250;
      props.viewModel.toggleCollapse?.(isCollapsed);
    };

    return () => {
      const vm = props.viewModel;
      const handleChooseRow = vm.chooseRow || noop;

      return (
        <bk-resize-layout
          v-slots={{
            main: () => (
              <div class='standalone-related-log-content'>
                <CommonHeader
                  title={props.title}
                  paramsInfo={vm.paramsInfo.value}
                  targetFields={vm.targetFields.value}
                />
                <div class='context-main standalone-related-log-main'>
                  <div class='data-filter-wraper'>
                    <DataFilter
                      ref={vm.dataFilterRef}
                      isRealTime={props.isRealTime}
                      onCopy={props.isRealTime ? vm.handleCopy || noop : undefined}
                      onFieldsConfigUpdate={vm.handleFieldsConfigUpdate}
                      onFixCurrentRow={vm.scrollToCurrentRow}
                      onHandleFilter={vm.handleFilter}
                      onTogglePoll={props.isRealTime ? vm.togglePoll || noop : undefined}
                    />
                  </div>
                  <div
                    ref={vm.scrollerRef}
                    class='dialog-log-markdown standalone-related-log-scroller'
                    v-loading={{
                      loading: vm.loading.value && !vm.isFilterEmpty.value,
                      indicator: vm.logList.value.length ? renderListRefreshSkeleton : renderLogListSkeleton,
                      showOverlay: !vm.logList.value.length,
                    }}
                  >
                    {vm.error.value ? (
                      <bk-exception
                        style='margin-top: 80px'
                        scene='part'
                        type='500'
                      >
                        <span>{vm.error.value}</span>
                      </bk-exception>
                    ) : vm.logList.value.length > 0 ? (
                      vm.isFilterEmpty.value ? (
                        <bk-exception
                          style='margin-top: 80px'
                          scene='part'
                          type='search-empty'
                        >
                          <span>{vm.t('搜索结果为空')}</span>
                        </bk-exception>
                      ) : (
                        <LogView
                          ref={vm.logViewRef}
                          filterKey={vm.activeFilterKey.value}
                          filterType={vm.filterType.value}
                          ignoreCase={vm.ignoreCase.value}
                          interval={vm.interval.value}
                          lightList={vm.highlightList.value}
                          logList={vm.logList.value}
                          maxLength={vm.maxLength}
                          reverseLogList={vm.reverseLogList.value}
                          shiftLength={vm.shiftLength}
                          showType={vm.showType.value}
                          isRealTimeLog={props.isRealTime}
                        />
                      )
                    ) : !vm.loading.value ? (
                      <bk-exception
                        style='margin-top: 80px'
                        scene='part'
                        type='empty'
                      >
                        <span>{vm.t('暂无数据')}</span>
                      </bk-exception>
                    ) : null}
                  </div>
                </div>
              </div>
            ),
            aside: () => (
              <LogResult
                ref={logResultRef}
                indexSetId={vm.indexSetId?.value || 0}
                logIndex={vm.rowIndex?.value || 0}
                retrieveParams={vm.retrieveParams?.value || {}}
                onChooseRow={handleChooseRow}
                onToggleCollapse={handleToggleCollapse}
              />
            ),
          }}
          class='standalone-related-log-resize'
          style='height: 100%'
          border={false}
          initial-divide={initialDivide.value}
          min={collapsedDivide}
          placement='bottom'
        ></bk-resize-layout>
      );
    };
  },
});
