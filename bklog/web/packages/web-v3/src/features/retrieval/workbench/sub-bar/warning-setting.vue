<template>
  <div
    ref="warnTriggerRef"
    class="warn-table-wrap"
    @click="isShowList"
  >
    <span
      v-log-tooltip.top="$t('告警')"
      :style="{ color: badgeCount !== 0 ? 'red' : '' }"
      :class="`bklog-icon bklog-${badgeCount !== 0 ? 'gaojing-filled' : 'gaojing-line'}`"
    ></span>
    <span class="warn-table-text">{{ $t('告警') }}</span>
    <t-badge :max-count="Infinity" show-zero
      v-if="ownPendingCount !== 0"
      style="margin-top: -12px; margin-left: -3px"
      :count="ownPendingCount"
      :color="'#ea3636'"
    />

    <div v-show="false">
      <div
        ref="refWarningSettingElement"
        class="bklog-warning-wrapper"
      >
        <t-tabs
          style="width: 580px; background-color: #fff"
          :value="active"
          theme="card"
          @change="handleTabChange"
        >
          <template #action>
            <div style="display: flex; align-items: center; justify-content: center; background-color: #f0f1f5">
              <div
                v-if="active === 'mission'"
                class="selector-owner"
              >
                {{ $t('我的') }}
                <t-switch
                  v-model="filterOwner"
                  class="selector-owner-switch"
                  size="small"
                ></t-switch>
              </div>
              <div
                v-if="active === 'mission'"
                class="selector-container"
              >
                <span
                  v-for="type in ['all', 'unHandle']"
                  :key="type"
                  class="option"
                  :class="{ selected: currentType === type }"
                  @click="handleRadioGroup(type)"
                >
                  {{ type === 'all' ? $t('全部') : $t('未恢复') }}
                </span>
              </div>
              <div
                class="selector-more"
                style="margin: 0 12px; color: #3a84ff; cursor: pointer"
                @click="handleJumpMonitor()"
              >
                {{ $t('更多')
                }}<span
                  style="margin-left: 4px"
                  class="bklog-icon bklog-jump"
                ></span>
              </div>
            </div>
          </template>

          <t-tab-panel
            v-for="item in panels"
            :key="item.name"
            :label="item.label"
            :value="item.name"
          >
            <template #label>
              <span class="panel-name">{{ $t(item.label) }}（{{ item.count }}）</span>
              <div
                v-if="item.name === active"
                class="active-box"
              ></div>
            </template>
            <!-- <bk-alert type="info">
              <span
                slot="title"
                style="cursor: pointer"
                @click="handleJumpMonitor"
                >{{ alertText }}</span
              >
            </bk-alert> -->
            <t-table
              v-if="active === 'mission'"
              :bordered="false"
              :columns="missionColumns"
              :data="missionLoading ? [] : recordListshow"
              :hover="true"
              :max-height="240"
              row-key="alert_id"
              size="small"
              stripe
              @sort-change="handleSortChange"
            >
              <template #empty>
                <div
                  v-if="missionLoading"
                  class="warning-table-skeleton"
                >
                  <div
                    v-for="index in 4"
                    :key="index"
                    class="warning-table-skeleton-row"
                  >
                    <span class="skeleton" style="width: 28%" />
                    <span class="skeleton" style="width: 22%" />
                    <span class="skeleton" style="width: 14%" />
                    <span class="skeleton" style="width: 12%" />
                    <span class="skeleton" style="width: 12%" />
                  </div>
                </div>
                <span
                  v-else
                  class="warning-table-empty"
                >{{ $t('暂无内容') }}</span>
              </template>
              <template #alert_name="{ row }">
                <div
                  v-log-overflow-tips="row.alert_name"
                  class="bklog-table-col-alert-name"
                  :style="{
                    color: '#3a84ff',
                    cursor: 'pointer',
                    '--severity-color': getLevelColor(row.severity),
                  }"
                  @click="handleViewWarningDetail(row)"
                >
                  <span class="severity-level"></span>{{ row.alert_name }}
                </div>
              </template>
              <template #first_anomaly_time="{ row }">
                <div>
                  {{ formatDate(row.first_anomaly_time, true) }}
                </div>
              </template>
              <template #status="{ row }">
                <div>
                  <span
                    :style="{ color: getColor(row.status), fontSize: '14px' }"
                    :class="getClass(row.status)"
                  />
                  {{ STATUS_NAME_MAP[row.status] }}
                </div>
              </template>
              <template #operation="{ row }">
                <div
                  style="color: #3a84ff; cursor: pointer"
                  @click="() => handleViewLogInfo(row)"
                >
                  {{ $t('查看日志') }}
                </div>
              </template>
            </t-table>
            <t-table
              v-if="active === 'config'"
              :bordered="false"
              :columns="configColumns"
              :data="strategyLoading ? [] : strategyList"
              :hover="true"
              :max-height="240"
              row-key="name"
              size="small"
              stripe
            >
              <template #empty>
                <div
                  v-if="strategyLoading"
                  class="warning-table-skeleton"
                >
                  <div
                    v-for="index in 4"
                    :key="index"
                    class="warning-table-skeleton-row"
                  >
                    <span class="skeleton" style="width: 32%" />
                    <span class="skeleton" style="width: 28%" />
                    <span class="skeleton" style="width: 22%" />
                  </div>
                </div>
                <span
                  v-else
                  class="warning-table-empty"
                >{{ $t('暂无内容') }}</span>
              </template>
              <template #name="{ row }">
                <div
                  class="strategy-name"
                  @click="handleStrategyInfoClick(row)"
                >
                  {{ t(row.name) }}
                </div>
              </template>
            </t-table>
          </t-tab-panel>
        </t-tabs>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import {
  MessagePlugin as TDesignMessage,
  Table as TTable,
  Tabs as TTabs,
  TabPanel as TTabPanel,
} from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
import { asDictionary } from '@/shared/utils/typed-record';

  import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
  import axios from 'axios';
  
  import { formatDate } from '@/shared/lib/util';
  import PopInstanceUtil from '@/shared/global/pop-instance-util';
  import useLocale from '@/shared/composables/use-locale';
  import useStore from '@/shared/composables/use-store';
  import RequestPool from '@/app/state/request-pool';
  

  import { ConditionOperator } from '../../../../app/state/condition-operator';
  import useRetrieveHook from '../use-retrieve-hook';
  import { BK_LOG_STORAGE } from '../../../../app/state/store.type.ts';
  import RetrieveHelper, { RetrieveEvent } from '@/features/retrieval/retrieve-helper';

  const ALERT_BADGE_CANCEL_KEY = 'retrieveAlertBadgeCancelToken';
  const ALERT_LIST_CANCEL_KEY = 'retrieveAlertListCancelToken';
  const STRATEGY_LIST_CANCEL_KEY = 'retrieveStrategyListCancelToken';

  const { t } = useLocale();
  const store = useStore();

  const { resolveQueryParams, resolveCommonParams } = useRetrieveHook();

  const refWarningSettingElement = ref(null);
  const warnTriggerRef = ref(null);

  const PopInstanceUtilInstance = new PopInstanceUtil({
    refContent: refWarningSettingElement,
    arrow: false,
    newInstance: false,
    tippyOptions: {
      arrow: false,
      placement: 'bottom',
      hideOnClick: true,
      offset: [0, 6],
      appendTo: document.body,
    },
  });
  const panels = ref([
    { name: 'mission', label: '最近告警记录', count: 0 },
    { name: 'config', label: '策略', count: 0 },
  ]);
  const indexId = computed(() => store.state.indexId);
  const userMeta = computed(() => store.state.userMeta);
  // const alertText = computed(() => {
  //   if (active.value === 'mission') {
  //     return t('最多展示近10条告警，点击查看更多');
  //   }

  //   return t('最多展示近10条策略，点击查看更多');
  // });

  // 告警数量
  const badgeCount = ref(0);
  // 本人待处理数量
  const ownPendingCount = ref(0);

  const missionLoading = ref(false);
  const strategyLoading = ref(false);
  const filterOwner = ref(true);
  const active = ref('mission');
  const typeMap = asDictionary({
    all: 'ALL',
    unHandle: 'ABNORMAL',
  });

  const currentType = ref('all');
  const handleRadioGroup = (val: string) => {
    currentType.value = val;
    const type = typeMap[currentType.value];
    getAlertListData(type);
  };

  const recordList = ref([]);
  const originRecordList = ref([]);
  const strategyList = ref<(({ latest_time: string | number | Date; } & { latest_time_format: string; }))[]>([]);
  const recordListshow = computed(() => {
    if (filterOwner.value) {
      return recordList.value.filter(
        (item: any) =>
          item.assignee?.some((assignee: string) => assignee === userMeta.value.username) ||
          item.appointee?.some((appointee: string) => appointee === userMeta.value.username),
      );
    }
    return recordList.value;
  });

  const pageSize = 10;

  // 未恢复：ABNORMAL
  // 已恢复：RECOVERED
  // 已失效：CLOSED
  const STATUS_COLOR_MAP = asDictionary({
    CLOSED: '#979BA5',
    RECOVERED: '#2CAF5E',
    ABNORMAL: '#EA3636',
    DEFAULT: '#000000',
  });

  const STATUS_CLASS_MAP = asDictionary({
    CLOSED: 'bklog-icon bklog-shixiao',
    RECOVERED: 'bklog-icon bklog-circle-correct-filled',
    ABNORMAL: 'bklog-icon bklog-circle-alert-filled',
    DEFAULT: 'bklog-icon bklog-circle-alert-filled',
  });

  const STATUS_NAME_MAP = {
    ABNORMAL: t('未恢复'),
    RECOVERED: t('已恢复'),
    CLOSED: t('已失效'),
  };

  const LEVEL_COLOR_MAP = asDictionary({
    1: '#E71818',
    2: '#F59500',
    3: '#3A84FF',
    DEFAULT: '#000000',
  });

  // const LEVEL_CLASS_MAP = {
  //   1: 'bklog-icon bklog-weixian',
  //   2: 'bklog-icon bklog-circle-alert-filled',
  //   3: 'bklog-icon bklog-info-fill',
  //   DEFAULT: 'bklog-icon bklog-info-fill',
  // };

  // const LEVEL_NAME_MAP = {
  //   1: t('致命'),
  //   2: t('预警'),
  //   3: t('提醒'),
  // };
  // 函数优化
  const getColor = (status: string) => STATUS_COLOR_MAP[status] || STATUS_COLOR_MAP.DEFAULT;
  const getClass = (status: string) => STATUS_CLASS_MAP[status] || STATUS_CLASS_MAP.DEFAULT;
  const getLevelColor = (severity: number) => LEVEL_COLOR_MAP[severity] || LEVEL_COLOR_MAP.DEFAULT;
  // const getLevelClass = (severity: number) => LEVEL_CLASS_MAP[severity] || LEVEL_CLASS_MAP.DEFAULT;

  const handleTabChange = (value: string | number) => {
    active.value = value as string;
  };

  // 固定布局下 col 的 minWidth 不生效，「首次发生时间」会被均分挤窄后换行。
  // 给这一列明确宽度，表头再强制单行。
  const missionColumns = computed(() => [
    { colKey: 'alert_name', title: t('告警名称'), minWidth: 120 },
    { colKey: 'first_anomaly_time', title: t('首次发生时间'), width: 168, sorter: true },
    { colKey: 'duration', title: t('持续时间'), width: 96, align: 'right' },
    { colKey: 'status', title: t('状态'), width: 96 },
    { colKey: 'operation', title: t('操作'), width: 88 },
  ]);
  const configColumns = computed(() => [
    { colKey: 'name', title: t('策略'), ellipsis: true, minWidth: 180 },
    { colKey: 'query_string', title: t('监控项'), ellipsis: true },
    { colKey: 'latest_time_format', title: t('最近告警时间'), minWidth: 168, ellipsis: true },
  ]);

  // TDesign sort-change 归一为 V2 的 order 语义，保持原排序行为不变
  const handleSortChange = (sortInfo: { colKey?: string; descending?: boolean } | null) => {
    const order = sortInfo == null || sortInfo.descending === undefined ? null : sortInfo.descending ? 'descending' : 'ascending';
    if (!order) {
      recordList.value = originRecordList.value;
    }
    // 对数组进行排序
    recordList.value.sort((a, b) => {
      // 将字符串转换为 Date 对象
      // 返回比较结果
      return order === 'ascending'
        ? a.first_anomaly_time - b.first_anomaly_time
        : b.first_anomaly_time - a.first_anomaly_time;
    });
  };
  const isShowList = () => {
    // 固定挂载参照元素为按钮根节点，避免 e.target 在图标/文字子元素间漂移，
    // 导致 newInstance:false 复用的 tippy 实例永久锚定在首次点击的子元素上。
    const target = warnTriggerRef.value;
    if (!target) {
      return;
    }

    // 防御性修复：tippy 已隐藏但内部 isShowing 标志位未同步复位时，
    // show() 里的 `if (this.isShowing) return` 会静默吞掉点击，表现为按钮失效。
    if (!PopInstanceUtilInstance.isShown() && PopInstanceUtilInstance.isInstanceShowing()) {
      PopInstanceUtilInstance.setIsShowing(false);
    }

    if (!PopInstanceUtilInstance.isShown()) {
      loadAlertPanelData();
      PopInstanceUtilInstance.show(target);
    }
  };

  const getQueryString = () => {
    const timezone = store.state.indexItem.timezone;
    const [startTime, endTime] = store.state.indexItem.datePickerValue;

    return `queryString=metric:bk_log_search.index_set.${store.state.indexId}&from=${startTime}&to=${endTime}&timezone=${timezone}`;
  };

  const handleJumpMonitor = () => {
    const addressMap = asDictionary({
      mission: 'event-center',
      config: 'strategy-config',
    });
    if (active.value === 'mission') {
      const res = getQueryString();
      window.open(
        `${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/${addressMap[active.value]}?${res}`,
        '_blank',
        'noopener,noreferrer',
      );
      return;
    }

    window.open(
      `${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/${addressMap[active.value]}?filters=[{"key":"metric_id","value":["bk_log_search.index_set.${store.state.indexId}"]}]`,
      '_blank',
      'noopener,noreferrer',
    );
  };

  const handleViewWarningDetail = (row: { id: any; }) => {
    window.open(
      `${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/event-center/detail/${row.id}`,
      '_blank',
      'noopener,noreferrer',
    );
  };

  const handleStrategyInfoClick = (row: { strategy_id: any; }) => {
    window.open(
      `${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/strategy-config/detail/${row.strategy_id}`,
      '_blank',
      'noopener,noreferrer',
    );
  };

  const isCurrentIndexRequest = (requestIndexId: string | number) => requestIndexId === indexId.value;

  const requestAlertList = (status: string, requestIndexId: string | number, cancelTokenKey: string) => {
    RequestPool.execCanceToken(cancelTokenKey);
    return ServicesInstance.alertStrategy.alertList(
      {
        params: {
          index_set_id: requestIndexId,
        },
        data: {
          status,
          page_size: pageSize,
          space_uid: store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID],
        },
      },
      { cancelToken: RequestPool.getCancelToken(cancelTokenKey) },
    );
  };

  /**
   * 获取告警角标数量
   * 角标口径与列表不同：已屏蔽的告警不应再红点提醒，因此固定使用 NOT_SHIELDED_ABNORMAL
   */
  const getAlertBadgeCount = async () => {
    const requestIndexId = indexId.value;
    try {
      if (!requestIndexId) {
        return;
      }

      const res = await requestAlertList('NOT_SHIELDED_ABNORMAL', requestIndexId, ALERT_BADGE_CANCEL_KEY);
      if (!isCurrentIndexRequest(requestIndexId)) {
        return;
      }
      const list = res?.data || [];

      badgeCount.value = list.length;
      ownPendingCount.value = list.filter((item: { assignee: any[]; appointee: any[]; }) => {
        return (
          item.assignee?.some((assignee: string) => assignee === userMeta.value.username) ||
          item.appointee?.some((appointee: string) => appointee === userMeta.value.username)
        );
      }).length;
    } catch (e) {
      if (axios.isCancel(e)) {
        return;
      }
      console.warn(e);
    }
  };

  /**
   * 获取告警列表
   * @param val
   * ALL - 表示查询全部告警记录;
   * ABNORMAL - 表示查询未恢复的告警记录，含已屏蔽;
   * MY_ASSIGNEE - 表示我收到的告警记录
   */
  let missionRequestSeq = 0;
  const getAlertListData = async (val: string) => {
    const requestIndexId = indexId.value;
    if (!requestIndexId) {
      return;
    }

    const requestSeq = ++missionRequestSeq;
    recordList.value = [];
    missionLoading.value = true;
    try {
      const res = await requestAlertList(val, requestIndexId, ALERT_LIST_CANCEL_KEY);
      if (requestSeq !== missionRequestSeq || !isCurrentIndexRequest(requestIndexId)) {
        return;
      }

      recordList.value = res?.data || [];
      originRecordList.value = recordList.value;
    } catch (e) {
      if (axios.isCancel(e)) {
        return;
      }
      console.warn(e);
    } finally {
      if (requestSeq === missionRequestSeq && isCurrentIndexRequest(requestIndexId)) {
        missionLoading.value = false;
      }
    }
  };

  /**
   * 获取策略列表
   */
  let strategyRequestSeq = 0;
  const getStrategyDate = async () => {
    const requestIndexId = indexId.value;
    if (!requestIndexId) {
      return;
    }

    const requestSeq = ++strategyRequestSeq;
    strategyList.value = [];
    RequestPool.execCanceToken(STRATEGY_LIST_CANCEL_KEY);
    strategyLoading.value = true;

    try {
      const res = await ServicesInstance.alertStrategy.strategyList(
        {
          params: {
            index_set_id: requestIndexId,
          },
          data: {
            page_size: pageSize,
            space_uid: store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID],
          },
        },
        { cancelToken: RequestPool.getCancelToken(STRATEGY_LIST_CANCEL_KEY) },
      );
      if (requestSeq !== strategyRequestSeq || !isCurrentIndexRequest(requestIndexId)) {
        return;
      }

      (res?.data || []).forEach((element: { latest_time: string|number|Date; }) => {
        strategyList.value.push(
          Object.assign({}, element, {
            latest_time_format: element.latest_time ? formatDate(element.latest_time, true) : '--',
          }),
        );
      });

      panels.value[1].count = res?.data.length || 0;
    } catch (e) {
      if (axios.isCancel(e)) {
        return;
      }
      console.warn(e);
    } finally {
      if (requestSeq === strategyRequestSeq && isCurrentIndexRequest(requestIndexId)) {
        strategyLoading.value = false;
      }
    }
  };

  const cancelAlertRequests = () => {
    RequestPool.execCanceToken(ALERT_BADGE_CANCEL_KEY);
    RequestPool.execCanceToken(ALERT_LIST_CANCEL_KEY);
    RequestPool.execCanceToken(STRATEGY_LIST_CANCEL_KEY);
  };

  const resetAlertPanelData = () => {
    badgeCount.value = 0;
    ownPendingCount.value = 0;
    recordList.value = [];
    originRecordList.value = [];
    strategyList.value = [];
    panels.value[1].count = 0;
    missionLoading.value = false;
    strategyLoading.value = false;
  };

  const loadAlertPanelData = () => {
    const type = typeMap[currentType.value];
    getAlertListData(type);
    getStrategyDate();
  };

  const handleViewLogInfo = (row: { first_anomaly_time: number; end_time: number; id: any; }) => {
    const startTime = row.first_anomaly_time * 1000;
    const endTime = row.end_time * 1000 || Date.now();

    ServicesInstance.alertStrategy.getLogRelatedInfo({
        params: {
          index_set_id: indexId.value,
        },
        query: {
          alert_id: row.id,
          bk_biz_id: store.state.bkBizId,
        },
      })
      .then(resp => {
        if (resp.result) {
          const { query_string: queryString, agg_condition: aggCondition } = resp.data;

          const params = {
            search_mode: null,
            addition: aggCondition.map((item: { key: any; method: any; value: any; condition: any; }) => {
              const instance = new ConditionOperator({
                field: item.key,
                operator: item.method,
                value: item.value,
                relation: item.condition,
              });
              return instance.formatApiOperatorToFront();
            }),
            keyword: queryString,
          };
          resolveCommonParams(params).then(() => {
            resolveQueryParams(params, true).then(res => {
              if (res) {
                store.commit('updateStorage', { [BK_LOG_STORAGE.SEARCH_TYPE]: 1 });
                store.commit('updateIndexItemParams', {
                  start_time: startTime,
                  end_time: endTime,
                  datePickerValue: [startTime, endTime],
                });
                store.dispatch('requestIndexSetQuery', { isPagination: false });
                RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
                PopInstanceUtilInstance.hide();
              }
            });
          });

          return;
        }

        TDesignMessage("error", { content: resp.message });
      })
      .catch(err => {
        TDesignMessage("error", { content: err.message });
      });
  };

  onMounted(() => {
    if (indexId.value) {
      getAlertBadgeCount();
    }
  });

  onUnmounted(() => {
    cancelAlertRequests();
    PopInstanceUtilInstance?.uninstallInstance();
  });

  // 索引集切换时只刷新角标；策略列表等面板打开再拉，避免占满连接挡住检索
  watch(
    () => indexId.value,
    () => {
      cancelAlertRequests();
      resetAlertPanelData();

      if (!indexId.value) {
        return;
      }

      getAlertBadgeCount();
      if (PopInstanceUtilInstance.isShown()) {
        loadAlertPanelData();
      }
    },
  );
  watch(
    () => recordListshow.value.length,
    newLength => {
      panels.value[0].count = newLength;
    },
  );
</script>
<style lang="scss">
  .warn-table-wrap {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 70px;
    height: 32px;
    font-size: 12px;
    cursor: pointer;

    .bklog-icon {
      margin: 0 6px 0 0;
      font-size: 16px;
    }
  }

  .tippy-content:has(.bklog-warning-wrapper) {
    padding: 0;
  }

  .bklog-warning-wrapper {
    .t-tabs,
    .t-tabs__content,
    .t-tab-panel {
      background-color: #fff;
    }

    .t-tabs__header,
    .t-tabs__nav,
    .t-tabs__operations,
    .t-tabs__nav-container.t-tabs__nav--card {
      height: 42px;
      background-color: #f0f1f5;
    }

    .t-tabs__operations--right {
      display: flex;
      align-items: center;
      height: 42px;
    }

    .t-tabs__nav-item.t-tabs__nav--card {
      height: 42px;
      padding: 0 16px;
      color: #313238;
      background-color: transparent;
      border: none;

      .t-tabs__nav-item-wrapper {
        height: 42px;
        margin: 0;
        padding: 0;
      }

      .panel-name {
        font-size: 13px;
        line-height: 42px;
        color: #313238;
      }

      &:hover:not(.t-is-active) {
        background-color: transparent;
      }

      &.t-is-active {
        color: #313238;
        background-color: #fff;

        &::before {
          position: absolute;
          top: 0;
          left: 0;
          z-index: var(--bklog-z-base);
          width: 100%;
          height: 5px;
          content: '';
          background-color: #3a84ff;
        }
      }
    }

    .active-box {
      display: none;
    }

    .t-tabs__content {
      padding: 0;
    }

    .t-table {
      font-size: 12px;
      color: #63656e;

      .t-table__content {
        border: none;
      }

      th,
      td {
        height: 32px;
        padding: 0 16px;
        font-size: 12px;
        line-height: 32px;
        border-bottom: none;
      }

      thead th {
        font-weight: 400;
        color: #63656e;
        white-space: nowrap;
        overflow-wrap: normal;
        background-color: #fff;
        border-bottom: 1px solid #dcdee5;

        .t-table__th-cell-inner,
        .t-table__cell--title {
          white-space: nowrap;
        }
      }

      .t-table__empty {
        padding: 0;
      }

      .warning-table-empty {
        display: block;
        padding: 48px 0;
        color: #979ba5;
      }

      .warning-table-skeleton-row {
        display: flex;
        align-items: center;
        height: 32px;
        padding: 0 16px;
        gap: 16px;

        .skeleton {
          display: inline-block;
          height: 12px;
          background: linear-gradient(90deg, #f0f2f5 25%, #e6e9ed 50%, #f0f2f5 75%);
          background-size: 400% 100%;
          border-radius: 2px;
          animation: warning-table-shimmer 1.4s infinite linear;
        }
      }

      @keyframes warning-table-shimmer {
        0% {
          background-position: 200% 0;
        }

        100% {
          background-position: -200% 0;
        }
      }

      &.t-table--striped > .t-table__content > table > tbody > tr {
        background-color: #fff;

        &:nth-of-type(odd) {
          background-color: #fafbfd;
        }
      }
    }

    .strategy-name {
      overflow: hidden;
      color: #3a84ff;
      text-overflow: ellipsis;
      white-space: nowrap;
      cursor: pointer;
    }

    .bklog-table-col-alert-name {
      position: relative;
      padding-left: 4px;

      .severity-level {
        position: absolute;
        top: 2px;
        left: 0;
        display: inline-block;
        min-width: 2px;
        min-height: 14px;
        margin-right: 2px;
        background-color: var(--severity-color);
      }
    }
  }

  .selector-owner {
    display: flex;
    align-items: center;
    margin-right: 10px;

    .selector-owner-switch {
      margin-left: 5px;
    }
  }

  .selector-container {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 112px;
    height: 32px;
    padding: 4px 4px;
    font-size: 12px;
    background-color: #dcdee5;
    border-radius: 4px;
  }

  .selector-more {
    font-size: 12px;
  }

  .option {
    display: flex; /* 使用 flex 布局 */
    flex: 1;
    align-items: center; /* 垂直居中 */
    justify-content: center; /* 水平居中 */
    width: 100%;
    height: 100%;
    color: #4d4f56;
    cursor: pointer;
    border-radius: 2px;
    transition: background-color 0.3s;
  }

  .option.selected {
    color: #3a84ff; /* 蓝色 */
    background-color: #ffffff;
  }
</style>
