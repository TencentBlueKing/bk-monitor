<!--
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
-->
<template>
  <article
    v-bkloading="{ isLoading: loading }"
    class="config-history"
  >
    <!--友情提示-->
    <section
      v-show="tableData.length > 0 && tipShow"
      class="config-history-tip"
    >
      <div class="tip-left">
        <span class="icon-monitor icon-tips left-icon" />
        <span class="left-title ml10"> {{ $t('仅保留最近30天的历史记录') }} </span>
      </div>
      <bk-button
        text
        class="tip-right"
        @click="handleHideTips"
      >
        {{ $t('知道了!') }}
      </bk-button>
    </section>
    <!--历史列表-->
    <section
      v-show="tableData.length > 0"
      class="config-history-content"
    >
      <bk-table
        :data="tableData"
        @row-click="handleRowClick"
      >
        <bk-table-column
          :label="$t('导入时间')"
          prop="createTime"
        />
        <bk-table-column
          :label="$t('操作人')"
          prop="createUser"
        >
          <template #default="{ row }">
            <bk-user-display-name
              v-if="row.createUser"
              :user-id="row.createUser"
            />
            <template v-else>--</template>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('执行结果')"
          width="220"
        >
          <template #default="{ row }">
            <div
              v-if="['upload', 'importing'].includes(row.status)"
              class="status-col"
            >
              <div class="status-item">
                <span class="status-runing icon-monitor icon-loading" />
                <span> {{ $t('导入中') }} </span>
              </div>
            </div>
            <div
              v-else
              class="status-col"
            >
              <div
                v-for="(value, name, index) of row.detail"
                v-show="value"
                :key="index"
                class="status-item"
              >
                <span :class="`status-${statusMap[name] ? statusMap[name].status : 'failed'}`" />
                <span>{{ getStatusText(name, row.detail) }}</span>
              </div>
            </div>
          </template>
        </bk-table-column>
      </bk-table>
    </section>
    <!--列表空数据-->
    <section
      v-show="tableData.length === 0"
      class="config-history-empty"
    >
      <span class="empty-icon"><i class="icon-monitor icon-hint" /></span>
      <span class="empty-drop"> {{ $t('未发现导入记录') }} </span>
      <span class="empty-tip"> {{ $t('仅保留最近30天的历史记录') }} </span>
    </section>
  </article>
</template>
<script>
import { mapActions } from 'vuex';

import { importConfigMixin } from '../../../common/mixins';
import { SET_NAV_ROUTE_LIST } from '../../../store/modules/app';

export default {
  name: 'ImportConfigurationHistory',
  mixins: [importConfigMixin], // 导入配置定时任务相关
  data() {
    return {
      // 表格数据
      tableData: [],
      // 状态Map
      statusMap: {
        successCount: {
          name: this.$t('成功'),
          status: 'success',
        },
        failedCount: {
          name: this.$t('失败'),
          status: 'failed',
        },
      },
      loading: false,
      tipShow: true,
      // tips过期时间 30 天（毫秒）
      expire: 3600000 * 24 * 30,
    };
  },
  created() {
    this.handleInit();
    this.updateNavData(this.$t('导入历史'));
  },
  methods: {
    ...mapActions('import', ['getHistoryList']),
    updateNavData(name = '') {
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, [{ name, id: '' }]);
    },
    async handleInit() {
      this.loading = true;
      // 判断提示信息是否过期
      if (window.localStorage) {
        const expireTime = window.localStorage.getItem('__import-history-tip__');
        this.tipShow = new Date().getTime() > expireTime;
      }
      this.tableData = await this.getHistoryList();
      this.handleSetRuningQueue();
      this.loading = false;
    },
    // 设置运行队列，刷新数据
    handleSetRuningQueue() {
      // taskQueue from mixin
      this.taskQueue = this.tableData.filter(item => ['upload', 'importing'].includes(item.status));
    },
    // 任务队列调用函数 mixin内部调用
    async handleQueueCallBack() {
      this.tableData = await this.getHistoryList();
      // 移除队列中不在运行中的任务
      this.taskQueue.forEach((item, index) => {
        this.tableData.forEach(row => {
          if (item.id === row.id && row.status === 'imported') {
            this.taskQueue.splice(index, 1);
          }
        });
      });
    },
    getStatusText(countName, detail) {
      if (countName === 'successCount') {
        return detail.failedCount ? this.$t('{0}个成功', [detail[countName]]) : this.$t('全部成功');
      }
      if (countName === 'failedCount') {
        return detail.failedCount ? this.$t('{0}个失败', [detail[countName]]) : this.$t('全部失败');
      }
    },
    handleRowClick(row) {
      this.$router.push({
        name: 'import-configuration-importing',
        params: {
          id: row.id,
        },
      });
    },
    handleHideTips() {
      if (window.localStorage) {
        const dateTime = new Date().getTime() + this.expire;
        window.localStorage.setItem('__import-history-tip__', dateTime);
        this.tipShow = false;
      }
    },
  },
};
</script>
<style lang="scss" scoped>
@import '../../../theme/index';

$statusColors: #94f5a4 #fd9c9c #3a84ff;
$statusBorderColors: #2dcb56 #ea3636 #3a84ff;
$tipBackground: #f0f8ff;
$tipBorderColor: #a3c5fd;
$emptyTipColor: #979ba5;

@mixin layout-flex($flexDirection: row, $alignItems: stretch, $justifyContent: flex-start) {
  display: flex;
  flex-direction: $flexDirection;
  align-items: $alignItems;
  justify-content: $justifyContent;
}

@mixin row-status($i: 1) {
  width: 8px;
  height: 8px;
  margin-right: 10px;
  background: nth($statusColors, $i);
  border: 1px solid nth($statusBorderColors, $i);
  border-radius: 50%;
}

.config-history {
  min-height: 100%;

  :deep(.bk-table-row) {
    cursor: pointer;
  }

  &-tip {
    height: 36px;
    padding: 0 12px;
    margin-bottom: 10px;
    background: $tipBackground;
    border-radius: 2px;

    @include layout-flex(row, center, space-between);
    @include border-1px($tipBorderColor);

    .tip-left {
      @include layout-flex(row, center, flex-start);
    }

    .left-title {
      color: $defaultFontColor;
    }

    .left-icon {
      margin-top: 2px;
      font-size: 14px;
      color: $primaryFontColor;
    }

    .tip-right {
      font-size: 12px;
    }
  }

  &-content {
    .status-col {
      @include layout-flex(row, center);
    }

    .status-item {
      height: 20px;
      margin-right: 18px;

      @include layout-flex(row, center);
    }

    .status-runing {
      width: 16px;
      height: 16px;
      margin-right: 6px;
      margin-left: -4px;
      font-size: 16px;
      color: nth($statusColors, 3);
      animation: button-icon-loading 1s linear infinite;
    }

    .status-success {
      @include row-status(1);
    }

    .status-failed {
      @include row-status(2);
    }
  }

  &-empty {
    @include layout-flex(column, center);

    .empty-icon {
      width: 42px;
      height: 42px;
      margin-top: 226px;
      font-size: 42px;
      color: $slightFontColor;
    }

    .empty-drop {
      margin-top: 6px;
      font-size: 14px;
      font-weight: bold;
      line-height: 19px;
      color: $defaultFontColor;
    }

    .empty-tip {
      margin-top: 6px;
      line-height: 16px;
      color: $emptyTipColor;
    }
  }
}
</style>
