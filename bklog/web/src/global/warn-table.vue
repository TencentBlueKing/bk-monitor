<template>
  <div>
    <!-- {{ t('告警') }} -->
    <div
      class="warn-table-wrap"
      @click="isShowList()"
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
    </div>
    <div
      v-if="isShow"
      class="warn-wrapper"
    >
      <bk-tab
        style="width: 560px"
        :active.sync="active"
        :active-bar="activeBar"
        type="card"
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
            <div style="margin: 0 12px; color: #3a84ff; cursor: pointer">
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
          <bk-table
            v-if="active === 'mission'"
            v-bkloading="{ isLoading: loading }"
            :data="recordList"
            :empty-text="$t('暂无内容')"
            :key="tableKey"
            :max-height="200"
            :outer-border="false"
            :row-border="false"
            @sort-change="handleSortChange"
          >
            <bk-table-column
              :label="$t('告警名称')"
              min-width="100"
            >
              <template #default="{ row }">
                <div style="color: #3a84ff; cursor: pointer">
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
                  {{ formatDate(row.first_anomaly_time)}}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('持续时间')"
              align="right"
              prop="duration"
            >
            </bk-table-column>
            <bk-table-column :label="$t('状态')" min-width="90">
              <template #default="{ row }">
                <div>
                  <span
                    :style="{ color: getColor(row.status), fontSize: '14px' }"
                    :class="getClass(row.status)"
                  />
                  {{ t(STATUS_NAME_MAP [row.status]) }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column :label="$t('告警级别')" min-width="90">
              <template #default="{ row }">
                <div :style="{ color: getLevelColor(row.severity), fontSize: '14px' }">
                  <span :class="getLevelClass(row.severity)" />
                  {{ t(LEVEL_NAME_MAP [row.severity]) }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('操作')"
            >
              <template #default="{ row }">
                <div style="color: #3a84ff; cursor: pointer">
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
                <div style="color: #3a84ff; cursor: pointer">
                  {{ t(row.name) }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('最近告警时间')"
              prop="latest_time"
            >
            </bk-table-column>
          </bk-table>
        </bk-tab-panel>
      </bk-tab>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { onMounted, ref, watch } from 'vue';
  import $http from '@/api';
  import useLocale from '@/hooks/use-locale';
  import {  formatDate,  } from '@/common/util';
  import {  useRoute } from 'vue-router/composables';
  const { t } = useLocale();
  const route = useRoute();
  const panels = ref([
    { name: 'mission', label: '最近告警记录', count: 0 },
    { name: 'config', label: '策略', count: 0 },
  ]);
  const indexId = ref(0);
  const badgeCount = ref(0);
  const activeBar = {
    position: 'top',
    height: '6px',
  };
  const loading = ref(false);
  const active = ref('mission');
  const typeMap={
    'all':'ALL',
    'unHandle':'NOT_SHIELDED_ABNORMAL',
  }
  const currentType = ref('all');
  const handleRadioGroup = (val: string) => {
    currentType.value = val;
  };
  const tableKey = ref(1);
  const recordList = ref([]);
  const originRecordList = ref([]);
  const strategyList = ref([]);
  const isShow = ref(false);
//   未恢复：ABNORMAL
// 已恢复：RECOVERED
// 已失效：CLOSED
const STATUS_COLOR_MAP = {
  CLOSED: '#979BA5',
  RECOVERED: '#2CAF5E',
  ABNORMAL: '#EA3636',
  DEFAULT: '#000000'
};

const STATUS_CLASS_MAP = {
  CLOSED: 'bklog-icon bklog-shixiao',
  RECOVERED: 'bklog-icon bklog-circle-correct-filled',
  ABNORMAL: 'bklog-icon bklog-circle-alert-filled',
  DEFAULT: 'bklog-icon bklog-circle-alert-filled'
};

const STATUS_NAME_MAP = {
  ABNORMAL: '未恢复',
  RECOVERED: '已恢复',
  CLOSED: '已失效'
};

const LEVEL_COLOR_MAP = {
  1: '#E71818',
  2: '#F59500',
  3: '#3A84FF',
  DEFAULT: '#000000'
};

const LEVEL_CLASS_MAP = {
  1: 'bklog-icon bklog-weixian',
  2: 'bklog-icon bklog-circle-alert-filled',
  3: 'bklog-icon bklog-info-fill',
  DEFAULT: 'bklog-icon bklog-info-fill'
};

const LEVEL_NAME_MAP = {
  1: '致命',
  2: '预警',
  3: '提醒'
};
// 函数优化
const getColor = (status:string) => STATUS_COLOR_MAP[status] || STATUS_COLOR_MAP.DEFAULT;
const getClass = (status:string) => STATUS_CLASS_MAP[status] || STATUS_CLASS_MAP.DEFAULT;
const getLevelColor = (severity:number) => LEVEL_COLOR_MAP[severity] || LEVEL_COLOR_MAP.DEFAULT;
const getLevelClass = (severity:number) => LEVEL_CLASS_MAP[severity] || LEVEL_CLASS_MAP.DEFAULT;
  const handleSortChange = (	{ column  }:{ column  }) => {
    console.log(column.order,'column.order')
    if (!column.order) {
      recordList.value = originRecordList.value;
  }
  // 对数组进行排序
  recordList.value.sort((a, b) => {
  // 将字符串转换为 Date 对象
    // 返回比较结果
    return column.order === 'ascending' ? (a.first_anomaly_time - b.first_anomaly_time) : (b.first_anomaly_time - a.first_anomaly_time);
  });
  };
  const isShowList = () => {
    isShow.value = !isShow.value;
  if(isShow.value){
      if(active.value==='mission'){
        const type=typeMap[currentType.value];
        getAlertDate(type)
      }else{
        getStrategyDate()
      }
      tableKey.value += 1;
  }
  };
  const getAlertDate= async(val:string)=>{
    try {
      loading.value = true;
    // const res = await $http.request('alertStrategy/alertList',{
    //         params: {
    //           index_set_id:indexId.value
    //         },
    //         data: {
    //           status:val,
    //           page_size: 11,
    //     },
    //       });
    const res={
    data:[{
            "id": "1741686571487423209",
            "strategy_id": 1234567,
            "alert_name": "告警能力补齐-test3",
            "first_anomaly_time": 1741685940,
            "duration": "10m",
            "status": "CLOSED",
            "severity": 2
        },
        {
            "id": "1741686571487422183",
	        "strategy_id": 1234567,
            "alert_name": "告警能力补齐-test",
            "first_anomaly_time": 1741685940,
            "duration": "10m",
            "status": "ABNORMAL",
            "severity": 1
        },
        {
            "id": "1741685606487418037",
	        "strategy_id": 1234567,
            "alert_name": "告警能力补齐-test1",
            "first_anomaly_time": 1741685460,
            "duration": "11m",
            "status": "CLOSED",
            "severity": 2
        },
    ]
      };
          console.log(res,'res');
          badgeCount.value = val ==='NOT_SHIELDED_ABNORMAL'? res?.data.length||0 : 0;
          console.log(badgeCount.value,'badgeCount.value')
          recordList.value = res?.data||[];
          originRecordList.value=recordList.value;
          panels.value[0].count=res?.data.length||0;
        } catch (e) {
            console.warn(e);
    }finally{
      loading.value = false;
    }
  };
  const getStrategyDate= async()=>{
    try {
      loading.value = true;
    const res = await $http.request('alertStrategy/strategyList',{
            params: {
              index_set_id:indexId.value
            },
            data: {
              page_size: 11,
            },
          });
          console.log(res,'res');
          strategyList.value = res?.data||[];
          panels.value[1].count=res?.data.length||0;
          // const currentTab=panels.value.findIndex(item=>item.name===active.value);
          // panels.value[currentTab].count=res?.data.length||0;
        } catch (e) {
            console.warn(e);
    }finally{
      loading.value = false;
    }
  };
  onMounted(()=> {
    console.log(route,'router')
    const match = route.path.match(/\/retrieve\/(\d+)/); // 用正则表达式匹配数字
    if (match) {
      const number = match[1]; // 第一个捕获组
      indexId.value=Number(number);
    }
    getAlertDate('NOT_SHIELDED_ABNORMAL')
  });

  watch(
    () => active.value,
    (val: string) => {
      if(active.value==='mission'){
        const type=typeMap[currentType.value];
        getAlertDate(type)
      }else{
        getStrategyDate()
      }
      tableKey.value += 1;
    },
  );
  watch(
    () => currentType.value,
    (val: string) => {

      const type=typeMap[val];
      getAlertDate(type);
      tableKey.value += 1;
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

  .warn-wrapper {
    position: absolute;
    top: 53px;
    right: 20px;

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

  // .option:not(:last-child) {
  //   border-right: 1px solid #dcdcdc;
  // }
</style>
