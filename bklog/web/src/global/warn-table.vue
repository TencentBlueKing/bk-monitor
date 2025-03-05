<template>
  <div>
    <!-- {{ t('告警') }} -->
    <div
      class="warn-table-wrap"
      @click="isShowList()"
    >
      <span
        style="color: red"
        class="bklog-icon bklog-gaojing-filled"
      ></span
      >{{ t('告警') }}
      <bk-badge
        style="margin-top: -12px; margin-left: -3px"
        :count="2"
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
          >
            <bk-table-column
              :label="$t('告警名称')"
              min-width="100"
            >
              <template #default="{ row }">
                <div style="color: #3a84ff; cursor: pointer">
                  {{ t(row.name) }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('首次发生时间')"
              min-width="120"
              prop="firstTime"
              sortable="true"
            >
            </bk-table-column>
            <bk-table-column
              :label="$t('持续时间')"
              align="right"
              prop="lastingTime"
            >
            </bk-table-column>
            <bk-table-column :label="$t('状态')">
              <template #default="{ row }">
                <div>
                  <span
                    :style="{ color: row.state ? '#2CAF5E' : '#EA3636', fontSize: '14px' }"
                    :class="`bklog-icon bklog-circle-${row.state ? 'correct-filled' : 'alert-filled'}`"
                  />
                  {{ t(row.state ? '已恢复' : '未恢复') }}
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
            <bk-table-column :label="$t('告警级别')">
              <template #default="{ row }">
                <div :style="{ color: row.state ? '#E71818' : '#3A84FF', fontSize: '14px' }">
                  <span :class="`bklog-icon bklog-${row.state ? 'weixian' : 'circle-alert-filled'}`" />
                  {{ t(row.state ? '致命' : '提醒') }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('最近告警时间')"
              prop="firstTime"
            >
            </bk-table-column>
          </bk-table>
        </bk-tab-panel>
      </bk-tab>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref, watch } from 'vue';

  import useLocale from '@/hooks/use-locale';
  const { t } = useLocale();
  const panels = ref([
    { name: 'mission', label: '最近告警记录', count: 10 },
    { name: 'config', label: '策略', count: 7 },
  ]);
  const activeBar = {
    position: 'top',
    height: '6px',
  };
  const loading = ref(false);
  const active = ref('mission');
  const currentType = ref('all');
  const handleRadioGroup = (val: string) => {
    currentType.value = val;
  };
  const tableKey = ref(1);
  const recordList = [
    { name: '拨测任务策略', firstTime: '2021 10-10 00:00:00', lastingTime: '19m', state: false },
    { name: '拨测任务策略2', firstTime: '2021 10-10 00:00:00', lastingTime: '12m', state: false },
    { name: '拨测任务策略3', firstTime: '2021 10-20 00:00:00', lastingTime: '12m', state: false },
    { name: '拨测任务策略2', firstTime: '2021 13-10 00:00:00', lastingTime: '12m', state: true },
    { name: '拨测任务策略5', firstTime: '2021 16-10 00:00:00', lastingTime: '13m', state: true },
    { name: '拨测任务策略7', firstTime: '2021 00-10 00:00:00', lastingTime: '3m', state: true },
  ];
  const strategyList = [
    { name: '拨测任务策略', firstTime: '2021 10-10 00:00:00', state: false },
    { name: '拨测任务策略2', firstTime: '2021 10-10 00:00:00', state: false },
    { name: '拨测任务策略2', firstTime: '2021 13-10 00:00:00', state: true },
    { name: '拨测任务策略5', firstTime: '2021 16-10 00:00:00', state: true },
  ];
  const isShow = ref(false);
  const isShowList = () => {
    isShow.value = !isShow.value;
  };
  watch(
    () => active.value,
    (val: string) => {
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
