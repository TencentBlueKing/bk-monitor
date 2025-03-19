<template>
  <div
    class="warn-table-wrap"
    @click="isShowList"
  >
    <span
      :style="{ color: badgeCount !== 0 ? 'red' : '' }"
      :class="`bklog-icon bklog-${badgeCount !== 0 ? 'gaojing-filled' : 'gaojing-line'}`"
    ></span
    >{{ t('告警') }}
    <bk-badge
      v-if="badgeCount !== 0"
      style="margin-top: -12px; margin-left: -3px"
      :count="badgeCount"
      theme="danger"
    />

    <div v-show="false">
      <div
        ref="refWarningSettingElement"
        class="bklog-warning-wrapper"
      >
        <bk-tab
          style="width: 560px; min-height: 200px; background-color: #fff"
          :active.sync="active"
          :active-bar="activeBar"
          type="card"
          @tab-change="handleTabChange"
        >
          <template #setting>
            <div style="display: flex; align-items: center; justify-content: center; background-color: #f0f1f5">
              <div
                v-if="active === 'mission'"
                class="selector-container"
              >
                <span
                  v-for="type in ['all', 'unHandle']"
                  class="option"
                  :class="{ selected: currentType === type }"
                  :key="type"
                  @click="handleRadioGroup(type)"
                >
                  {{ type === 'all' ? '全部' : '未处理' }}
                </span>
              </div>
              <div
                style="margin: 0 12px; color: #3a84ff; cursor: pointer"
                @click="handleJumpMonitor()"
              >
                {{ t('更多')
                }}<span
                  style="margin-left: 4px"
                  class="bklog-icon bklog-jump"
                ></span>
              </div>
            </div>
          </template>

          <bk-tab-panel
            v-for="(item, index) in panels"
            :key="item.name"
            :label="item.label"
            :name="item.name"
          >
            <template #label>
              <span class="panel-name">{{ $t(item.label) }}（{{ item.count }}）</span>
              <div
                v-if="item.name === active"
                class="active-box"
              ></div>
            </template>
            <bk-alert type="info">
              <template #title>
                <span
                  style="cursor: pointer"
                  @click="handleJumpMonitor"
                  >{{ alertText }}</span
                >
              </template>
            </bk-alert>
            <bk-table
              v-if="active === 'mission'"
              v-bkloading="{ isLoading: loading }"
              :data="recordList"
              :empty-text="$t('暂无内容')"
              :key="tableKey"
              :max-height="200"
              :min-height="120"
              :outer-border="false"
              :row-border="false"
              @sort-change="handleSortChange"
            >
              <bk-table-column
                :label="$t('告警名称')"
                min-width="100"
              >
                <template #default="{ row }">
                  <div
                    style="color: #3a84ff; cursor: pointer"
                    @click="handleViewWarningDetail(row)"
                  >
                    {{ t(row.alert_name) }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('首次发生时间')"
                min-width="115"
                sortable="true"
              >
                <template #default="{ row }">
                  <div>
                    {{ formatDate(row.first_anomaly_time) }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('持续时间')"
                align="right"
                prop="duration"
              >
              </bk-table-column>
              <bk-table-column
                :label="$t('状态')"
                min-width="90"
              >
                <template #default="{ row }">
                  <div>
                    <span
                      :style="{ color: getColor(row.status), fontSize: '14px' }"
                      :class="getClass(row.status)"
                    />
                    {{ t(STATUS_NAME_MAP[row.status]) }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('告警级别')"
                min-width="90"
              >
                <template #default="{ row }">
                  <div :style="{ color: getLevelColor(row.severity), fontSize: '14px' }">
                    <span :class="getLevelClass(row.severity)" />
                    {{ t(LEVEL_NAME_MAP[row.severity]) }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('操作')">
                <template #default="{ row }">
                  <div
                    style="color: #3a84ff; cursor: pointer"
                    @click="() => handleViewLogInfo(row)"
                  >
                    {{ $t('查看日志') }}
                  </div>
                </template>
              </bk-table-column>
            </bk-table>
            <bk-table
              v-if="active === 'config'"
              v-bkloading="{ isLoading: loading }"
              :border="false"
              :data="strategyList"
              :empty-text="$t('暂无内容')"
              :key="tableKey"
              :max-height="200"
              :outer-border="false"
              :row-border="false"
            >
              <bk-table-column :label="$t('策略')">
                <template #default="{ row }">
                  <div
                    style="color: #3a84ff; cursor: pointer"
                    @click="handleStrategyInfoClick(row)"
                  >
                    {{ t(row.name) }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('最近告警时间')"
                prop="latest_time_format"
              >
              </bk-table-column>
            </bk-table>
          </bk-tab-panel>
        </bk-tab>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue';

  import { formatDate } from '@/common/util';
  import PopInstanceUtil from '@/global/pop-instance-util';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { bkMessage } from 'bk-magic-vue';

  import { ConditionOperator } from '../../../store/condition-operator';
  import useRetrieveHook from '../use-retrieve-hook';
  import $http from '@/api';
  const { t } = useLocale();
  const store = useStore();

  const { resolveQueryParams, resolveCommonParams } = useRetrieveHook();

  const refWarningSettingElement = ref(null);

  const PopInstanceUtilInstance = new PopInstanceUtil({
    refContent: refWarningSettingElement,
    arrow: false,
    newInstance: false,
    tippyOptions: {
      arrow: false,
      placement: 'bottom-end',
      hideOnClick: true,
      offset: [0, 0],
      appendTo: document.body,
    },
  });

  const panels = ref([
    { name: 'mission', label: '最近告警记录', count: 0 },
    { name: 'config', label: '策略', count: 0 },
  ]);
  const indexId = computed(() => store.state.indexId);
  const alertText = computed(() => {
    if (active.value === 'mission') {
      return t('最多展示近10条告警，点击查看更多');
    }

    return t('最多展示近10条策略，点击查看更多');
  });

  const badgeCount = ref(0);
  const activeBar = {
    position: 'top',
    height: '6px',
  };
  const loading = ref(false);
  const active = ref('mission');
  const typeMap = {
    all: 'ALL',
    unHandle: 'NOT_SHIELDED_ABNORMAL',
  };
  const currentType = ref('all');
  const handleRadioGroup = (val: string) => {
    currentType.value = val;
    const type = typeMap[currentType.value];
    getAlertListData(type);
  };

  const tableKey = ref(1);
  const recordList = ref([]);
  const originRecordList = ref([]);
  const strategyList = ref([]);

  const pageSize = 10;

  // 未恢复：ABNORMAL
  // 已恢复：RECOVERED
  // 已失效：CLOSED
  const STATUS_COLOR_MAP = {
    CLOSED: '#979BA5',
    RECOVERED: '#2CAF5E',
    ABNORMAL: '#EA3636',
    DEFAULT: '#000000',
  };

  const STATUS_CLASS_MAP = {
    CLOSED: 'bklog-icon bklog-shixiao',
    RECOVERED: 'bklog-icon bklog-circle-correct-filled',
    ABNORMAL: 'bklog-icon bklog-circle-alert-filled',
    DEFAULT: 'bklog-icon bklog-circle-alert-filled',
  };

  const STATUS_NAME_MAP = {
    ABNORMAL: '未恢复',
    RECOVERED: '已恢复',
    CLOSED: '已失效',
  };

  const LEVEL_COLOR_MAP = {
    1: '#E71818',
    2: '#F59500',
    3: '#3A84FF',
    DEFAULT: '#000000',
  };

  const LEVEL_CLASS_MAP = {
    1: 'bklog-icon bklog-weixian',
    2: 'bklog-icon bklog-circle-alert-filled',
    3: 'bklog-icon bklog-info-fill',
    DEFAULT: 'bklog-icon bklog-info-fill',
  };

  const LEVEL_NAME_MAP = {
    1: '致命',
    2: '预警',
    3: '提醒',
  };
  // 函数优化
  const getColor = (status: string) => STATUS_COLOR_MAP[status] || STATUS_COLOR_MAP.DEFAULT;
  const getClass = (status: string) => STATUS_CLASS_MAP[status] || STATUS_CLASS_MAP.DEFAULT;
  const getLevelColor = (severity: number) => LEVEL_COLOR_MAP[severity] || LEVEL_COLOR_MAP.DEFAULT;
  const getLevelClass = (severity: number) => LEVEL_CLASS_MAP[severity] || LEVEL_CLASS_MAP.DEFAULT;

  const handleTabChange = () => {
    tableKey.value += 1;
  };

  const handleSortChange = ({ column }: { column }) => {
    if (!column.order) {
      recordList.value = originRecordList.value;
    }
    // 对数组进行排序
    recordList.value.sort((a, b) => {
      // 将字符串转换为 Date 对象
      // 返回比较结果
      return column.order === 'ascending'
        ? a.first_anomaly_time - b.first_anomaly_time
        : b.first_anomaly_time - a.first_anomaly_time;
    });
  };
  const isShowList = e => {
    if (!PopInstanceUtilInstance.isShown()) {
      PopInstanceUtilInstance.show(e.target);
    }
  };

  const handleJumpMonitor = () => {
    const addressMap = {
      mission: 'event-center',
      config: 'strategy-config',
    };
    window.open(`${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/${addressMap[active.value]}`, '_blank');
  };

  const handleViewWarningDetail = row => {
    window.open(`${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/event-center/detail/${row.id}`, '_blank');
  };

  const handleStrategyInfoClick = row => {
    window.open(
      `${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/strategy-config/detail/${row.strategy_id}`,
      '_blank',
    );
  };

  /**
   * 获取告警列表
   * @param val
   * ALL - 表示查询全部告警记录;
   * NOT_SHIELDED_ABNORMAL - 表示查询未处理的告警记录;
   * MY_ASSIGNEE - 表示我收到的告警记录
   */
  const getAlertListData = async (val: string) => {
    try {
      loading.value = true;
      const res = await $http.request('alertStrategy/alertList', {
        params: {
          index_set_id: indexId.value,
        },
        data: {
          status: val,
          page_size: pageSize,
        },
      });

      if (val === 'NOT_SHIELDED_ABNORMAL') {
        badgeCount.value = res?.data.length;
      }

      recordList.value = res?.data || [];
      originRecordList.value = recordList.value;
      panels.value[0].count = res?.data.length || 0;
      tableKey.value += 1;
    } catch (e) {
      console.warn(e);
    } finally {
      loading.value = false;
    }
  };

  /**
   * 获取策略列表
   */
  const getStrategyDate = async () => {
    try {
      loading.value = true;
      strategyList.value.length = 0;
      strategyList.value = [];
      const res = await $http.request('alertStrategy/strategyList', {
        params: {
          index_set_id: indexId.value,
        },
        data: {
          page_size: pageSize,
        },
      });

      (res?.data || []).forEach(element => {
        strategyList.value.push(
          Object.assign({}, element, {
            latest_time_format: element.latest_time ? formatDate(element.latest_time) : '--',
          }),
        );
      });

      panels.value[1].count = res?.data.length || 0;
      tableKey.value += 1;
    } catch (e) {
      console.warn(e);
    } finally {
      loading.value = false;
    }
  };

  const handleViewLogInfo = row => {
    loading.value = true;
    $http
      .request('alertStrategy/getLogRelatedInfo', {
        params: {
          index_set_id: indexId.value,
        },
        query: {
          alert_id: row.id,
        },
      })
      .then(resp => {
        if (resp.result) {
          const { query_string, agg_condition } = resp.data;

          const params = {
            search_mode: null,
            addition: agg_condition.map(item => {
              const instance = new ConditionOperator({
                field: item.key,
                operator: item.method,
                value: item.value,
                relation: item.condition,
              });
              return instance.formatApiOperatorToFront();
            }),
            keyword: query_string,
          };
          resolveCommonParams(params);
          resolveQueryParams(params).then(res => {
            if (res) {
              store.dispatch('requestIndexSetQuery', { isPagination: false });
              PopInstanceUtilInstance.hide();
            }
          });
          return;
        }

        bkMessage({
          theme: 'error',
          message: resp.message,
        });
      })
      .catch(err => {
        bkMessage({
          theme: 'error',
          message: err.message,
        });
      })
      .finally(() => {
        loading.value = false;
      });
  };

  const setMounted = async () => {
    await getAlertListData('NOT_SHIELDED_ABNORMAL');

    const type = typeMap[currentType.value];
    getAlertListData(type);

    getStrategyDate();
  };

  onMounted(async () => {
    await setMounted();
  });

  // 索引集ID改变时，获取告警数量
  // 逻辑和第一次加载时一样
  watch(
    () => [indexId.value],
    () => {
      badgeCount.value = 0;
      setMounted();
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
    margin-left: 10px;
    font-size: 14px;
    color: #63656e;
    cursor: pointer;

    .bklog-icon {
      margin: 3px 6px 0 0;
    }
  }

  .bklog-warning-wrapper {
    .bk-tab-card {
      background-color: #fafbfd;

      .bk-tab-section {
        padding: 0px;
      }

      .bk-tab-header {
        /* stylelint-disable-next-line declaration-no-important */
        height: 42px !important;

        .bk-tab-header-setting {
          /* stylelint-disable-next-line declaration-no-important */
          height: 42px !important;

          /* stylelint-disable-next-line declaration-no-important */
          line-height: 42px !important;
        }

        .bk-tab-label-wrapper {
          color: #313238;
          background-color: #f0f1f5;

          .bk-tab-label-list {
            /* stylelint-disable-next-line declaration-no-important */
            height: 42px !important;
          }

          .bk-tab-label-item {
            font-size: 13px;

            /* stylelint-disable-next-line declaration-no-important */
            line-height: 42px !important;
          }

          .active-box {
            position: absolute;
            top: 0px;
            left: 0px;
            width: 100%;
            height: 5px;
            background-color: #3a84ff;
          }
        }
      }

      .bk-table-header-wrapper {
        th,
        .cell {
          height: 32px;
        }
      }

      .bk-table-body-wrapper {
        td {
          height: 32px;
          border-bottom: none;
        }
      }
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
    border: 1px solid #dcdcdc;
    border-radius: 4px;
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
    transition: background-color 0.3s;
  }

  .option.selected {
    color: #3a84ff; /* 蓝色 */
    background-color: #ffffff;
  }
</style>
