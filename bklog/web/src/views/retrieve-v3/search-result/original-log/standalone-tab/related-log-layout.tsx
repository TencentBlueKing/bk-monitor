import { defineComponent, nextTick, onMounted, ref, type PropType } from 'vue';

import LogView from '@/components/log-view/index.vue';

import CommonHeader from '../components/common-header';
import DataFilter from '../components/data-filter';
import LogResult from '../components/origin-log-result';

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

    onMounted(() => {
      nextTick(() => {
        logResultRef.value?.init?.();
      });
    });

    const noop = () => {};

    return () => {
      const vm = props.viewModel;
      const handleChooseRow = vm.chooseRow || noop;
      const handleToggleCollapse = vm.toggleCollapse || noop;
      const dataFilterListeners: Record<string, (..._args: any[]) => void> = {
        'fields-config-update': vm.handleFieldsConfigUpdate,
        'fix-current-row': vm.scrollToCurrentRow,
        'handle-filter': vm.handleFilter,
      };

      if (props.isRealTime) {
        dataFilterListeners.copy = vm.handleCopy || noop;
        dataFilterListeners['toggle-poll'] = vm.togglePoll || noop;
      }

      return (
        <bk-resize-layout
          class='standalone-related-log-resize'
          style='height: 100%'
          border={false}
          initial-divide={250}
          min={42}
          placement='bottom'
        >
          <div
            class='standalone-related-log-content'
            slot='main'
          >
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
                  on={dataFilterListeners}
                />
              </div>
              <div
                ref={vm.scrollerRef}
                class='dialog-log-markdown standalone-related-log-scroller'
                v-bkloading={{
                  isLoading: vm.loading.value && !vm.isFilterEmpty.value,
                  opacity: 0.6,
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
                      filter-key={vm.activeFilterKey.value}
                      filter-type={vm.filterType.value}
                      ignore-case={vm.ignoreCase.value}
                      interval={vm.interval.value}
                      light-list={vm.highlightList.value}
                      log-list={vm.logList.value}
                      max-length={vm.maxLength}
                      reverse-log-list={vm.reverseLogList.value}
                      shift-length={vm.shiftLength}
                      show-type={vm.showType.value}
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
          <LogResult
            ref={logResultRef}
            slot='aside'
            indexSetId={vm.indexSetId?.value || 0}
            logIndex={vm.rowIndex?.value || 0}
            retrieveParams={vm.retrieveParams?.value || {}}
            on-choose-row={handleChooseRow}
            on-toggle-collapse={handleToggleCollapse}
          />
        </bk-resize-layout>
      );
    };
  },
});
