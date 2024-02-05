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
    class="import-config"
    v-bkloading="{ isLoading: loading }"
  >
    <!--按钮组（统计信息）-->
    <section
      class="import-config-tag"
      v-show="historyId"
    >
      <div class="config-tag">
        <div class="bk-button-group">
          <bk-button
            v-for="item in tag.list"
            :key="item.status"
            :class="{ 'is-selected': tag.active === item.status }"
            @click="handleTagClick(item)"
          >
            {{ `${item.name}(${item.num})` }}
          </bk-button>
        </div>
        <bk-button
          class="ml10"
          :disabled="disabledBatchRetryBtn"
          hover-theme="primary"
          @click="handleBatchRetry"
        >
          <span class="icon-monitor icon-mc-retry" /> {{ $t('批量重试') }}
        </bk-button>
      </div>
    </section>
    <!--折叠内容-->
    <section
      class="import-config-content"
      :style="{ marginBottom: isScroll ? '34px' : '' }"
      ref="collapse"
    >
      <bk-collapse
        v-model="collapse.activeName"
        @item-click="handleClickCollapse"
      >
        <bk-collapse-item
          v-for="item in collapse.list"
          :key="item.name"
          :name="item.name"
          ext-cls="collapse-item"
        >
          <!--折叠title-->
          <template #default>
            <!--左侧名称-->
            <div class="collapse-item-left">
              <i
                class="bk-icon icon-play-shape collapse-item-icon"
                :class="{ 'icon-rotate': collapse.activeName.includes(item.name) }"
              />
              <span class="collapse-item-title">{{ getItemTitle(item) }}</span>
              <span
                class="collapse-item-mark"
                v-if="item.markName"
              >{{ item.markName }}</span>
            </div>
            <!--右侧状态-->
            <div
              class="collapse-item-right"
              v-show="table.statistics && table.statistics[item.name]"
            >
              <!-- eslint-disable-next-line vue/no-v-html -->
              <span>
                <template v-for="(val, status) in statusMap">
                  {{ `{0}个${statusMap[status].name}` }}
                  <i18n
                    v-if="table.statistics[item.name][status]"
                    :path="status === 'success' ? '{0} 个检测成功' : '{0} 个检测失败'"
                    :key="status"
                  >
                    <span :class="`total-${status}`">{{ table.statistics[item.name][status] }}</span>
                  </i18n>
                </template>
              </span>
            </div>
          </template>
          <!--折叠表格-->
          <template #content>
            <bk-table
              max-height="410"
              :ref="item.name"
              v-show="tableData(item.name)"
              :data="tableData(item.name)"
              row-key="uuid"
              @select="handleSelectChange"
              @select-all="handleSelectAll($event, item.name)"
            >
              <bk-table-column
                align="left"
                header-align="left"
                type="selection"
                width="40"
                :selectable="handleItemSelectable"
                reserve-selection
                v-if="!historyId && !item.markName"
              />
              <bk-table-column
                :label="$t('配置名称')"
                prop="name"
                width="205"
                align="left"
                header-align="left"
              />
              <bk-table-column
                :label="$t('监控对象')"
                prop="label"
                width="190"
              />
              <bk-table-column
                :label="$t('任务状态')"
                width="153"
                :render-header="renderHeader"
              >
                <template #default="{ row }">
                  <div
                    class="status-col"
                    v-if="statusMap[row.status]"
                  >
                    <span
                      v-if="row.status === 'importing'"
                      class="status-runing icon-monitor icon-loading"
                    />
                    <span
                      :class="'status-' + row.status"
                      v-else
                    />
                    <span>{{ statusMap[row.status].name }}</span>
                  </div>
                  <div
                    class="status-col"
                    v-else
                  >
                    <span class="status-failed" />
                    <span> {{ $t('状态未知') }} </span>
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('详情')">
                <template #default="{ row }">
                  <div class="detail-col">
                    <span>{{ row.errorMsg ? row.errorMsg : '--' }}</span>
                    <bk-button
                      v-show="historyId && row.status === 'failed'"
                      text
                      @click="handleRetry(row.uuid)"
                    >
                      {{ $t('重试') }}
                    </bk-button>
                  </div>
                </template>
              </bk-table-column>
            </bk-table>
          </template>
        </bk-collapse-item>
      </bk-collapse>
    </section>
    <!--底部按钮-->
    <section class="import-config-footer">
      <!--背景占位-->
      <div :class="{ 'footer-banner': isScroll }" />
      <!--按钮wrap 悬浮-->
      <div
        class="button1-wrap"
        @mouseover="historyId && disabledConfirmBtn && handleMouseOver($event)"
        @mouseleave="historyId && disabledConfirmBtn && handleMouseLeave($event)"
      >
        <bk-button
          theme="primary"
          class="mr10"
          :class="{ 'footer-button1': isScroll }"
          @click="handleImportClick"
          :disabled="disabledConfirmBtn"
        >
          {{ historyId ? $t('前往添加统一监控目标') : $t('导入') }}
        </bk-button>
      </div>
      <bk-button
        class="button-cancel"
        :class="{ 'footer-button2': isScroll }"
        :style="{ marginLeft: isScroll && id ? '182px' : '' }"
        @click="handleImportCancel"
      >
        {{ historyId ? $t('暂不添加') : $t('取消') }}
      </bk-button>
    </section>
  </article>
</template>
<script>
import { mapActions } from 'vuex';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { debounce } from 'throttle-debounce';

import { transformDataKey } from '../../../../monitor-common/utils/utils';

export default {
  name: 'ImportConfiguration',
  props: {
    // history id
    id: {
      type: [Number, String],
      default: 0
    },
    // 导入界面数据
    importData: {
      type: Object,
      default: () => ({
        configList: []
      })
    }
  },
  data() {
    return {
      tag: {
        list: [
          {
            name: this.$t('全部'),
            num: 0,
            status: 'total'
          },
          {
            name: this.$t('成功'),
            num: 0,
            status: 'success'
          },
          {
            name: this.$t('失败'),
            num: 0,
            status: 'failed'
          },
          {
            name: this.$t('执行中'),
            num: 0,
            status: 'importing'
          }
        ],
        active: 'total'
      },
      collapse: {
        list: [
          {
            name: 'collect',
            title: this.$t('采集配置')
          },
          {
            name: 'strategy',
            title: this.$t('策略配置')
          },
          {
            name: 'view',
            title: this.$t('视图配置')
          },
          {
            name: 'bkmonitor.models.fta.plugin',
            title: this.$t('被关联插件'),
            markName: this.$t('被关联')
          }
        ],
        activeName: ['collect']
      },
      configStatusMap: {
        success: {
          name: this.$t('检测成功'),
          status: 'success'
        },
        failed: {
          name: this.$t('检测失败'),
          status: 'failed'
        }
      },
      detailStatusMap: {
        success: {
          name: this.$t('成功'),
          status: 'success'
        },
        failed: {
          name: this.$t('失败'),
          status: 'failed'
        },
        importing: {
          name: this.$t('导入中'),
          status: 'importing'
        }
      },
      // 当前statusMap
      statusMap: {},
      statusFilterArr: [
        {
          text: this.$t('检测成功'),
          value: 'success'
        },
        {
          text: this.$t('检测失败'),
          value: 'fail'
        }
      ],
      table: {
        list: [],
        statistics: {},
        firstCheckedAll: [],
        runingQueue: [],
        timer: null,
        interval: 300,
        selection: [],
        filterStatusName: this.$t('任务状态'),
        taskId: 0
      },
      listenResize() {},
      historyId: this.id,
      batchRetryLoading: false,
      isScroll: false,
      loading: false,
      popoverInstance: null
    };
  },
  computed: {
    disabledBatchRetryBtn() {
      return (
        this.table.runingQueue.length !== 0 || this.table.list.filter(item => item.status === 'failed').length === 0
      );
    },
    disabledConfirmBtn() {
      if (!this.id || !this.historyId) {
        return !this.table.list?.some(item => item.checked);
      }
      const hasRepeat = {};
      return (
        this.table.list
        && !this.table.list.every((item, index) => {
          if (index === 0) {
            hasRepeat[item.label] = true;
          }
          return !!hasRepeat[item.label];
        })
      );
    },
    tableData() {
      // 从list中筛选出每个表格的数据
      return type => this.table.list.filter((item) => {
        const curActive = this.tag.active === 'total' || item.status === this.tag.active;
        return item.type === type && curActive;
      });
    }
  },
  watch: {
    'table.runingQueue': {
      handler(v) {
        if (v && v.length > 0 && !this.table.timer) {
          // 开启定时任务
          this.handleRunTimer();
        } else if (!v || v.length === 0) {
          // 当且仅当运行队列为空时才能移除timer
          // 结束所有任务
          clearTimeout(this.table.timer);
          this.table.timer = null;
        }
      },
      immediate: true
    },
    id: {
      handler(value, old) {
        if (value !== old) {
          this.statusMap = this.detailStatusMap;
          this.historyId = this.id;
          this.handleInit();
        } else {
          this.statusMap = this.configStatusMap;
        }
      }
    }
  },
  created() {
    // just do it
    this.handleInit();
  },
  mounted() {
    this.listenResize = debounce(200, v => this.handleResize(v));
    addListener(this.$el, this.listenResize);
  },
  beforeRouteLeave(to, from, next) {
    this.table.runingQueue = [];
    next();
  },
  beforeDestroy() {
    this.table.runingQueue = [];
    removeListener(this.$el, this.handleResize);
  },
  methods: {
    ...mapActions('import', ['handleImportConfig', 'getHistoryDetail']),
    async handleInit() {
      if (!this.id) {
        await this.handleInitImportConfigData();
      } else {
        await this.handleInitDetailConfigData();
      }
      // 首次展开勾选表格所有项
      this.handleClickCollapse();
    },
    // 开始导入界面数据初始化
    async handleInitImportConfigData() {
      this.statusMap = this.configStatusMap;
      const data = transformDataKey(this.importData);
      // todo
      this.table.taskId = data.importHistoryId;
      this.table.list = data.configList.map((item) => {
        if (item.type !== 'bkmonitor.models.fta.plugin') {
          item.checked = item.fileStatus === 'success'; // 默认勾选所有成功项
        }
        item.status = item.fileStatus;
        return item;
      });
      this.table.statistics = this.handleCountData(data);
    },
    // 导入中界面数据初始化
    async handleInitDetailConfigData() {
      this.loading = true;
      this.statusMap = this.detailStatusMap;
      const data = await this.getHistoryDetail(this.id || this.table.taskId).catch(() => {
        this.loading = false;
      });
      this.table.list = data.configList.map((item) => {
        item.status = item.importStatus;
        return item;
      });
      this.table.statistics = this.handleCountData(data);
      this.tag.list.forEach((item) => {
        item.num = this.table.statistics.allCount[item.status] || 0;
      });
      // 刷新运行中的任务
      this.handlePushRuningTask();
      this.loading = false;
    },
    // 规整统计数据
    handleCountData(data) {
      if (!data) return {};
      return {
        collect: data.collectCount,
        plugin: data.pluginCount,
        strategy: data.strategyCount,
        view: data.viewCount,
        allCount: data.allCount
      };
    },
    async handleRunTimer() {
      const interval = (cb) => {
        const fn = async () => {
          await cb();
          if (this.table.runingQueue.length === 0) {
            return;
          }
          this.table.timer = setTimeout(() => {
            fn();
          }, this.table.interval);
        };
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        this.table.timer = setTimeout(fn, this.table.interval);
      };
      interval(async () => {
        // todo
        const data = await this.getHistoryDetail(this.id || this.historyId);
        this.handleChangeStatus(data);
      });
    },
    handlePushRuningTask() {
      const uuids = this.table.list.filter(item => item.status === 'importing');
      this.table.runingQueue.push(...uuids);
    },
    handleChangeStatus(data) {
      if (!data?.configList) return;
      data.configList.forEach((current) => {
        this.table.list.forEach((item) => {
          if (current.uuid === item.uuid && this.table.runingQueue.includes(current.uuid)) {
            // 更新当前item最新状态
            item.status = current.importStatus;
            // 如果当前状态不为importing则移除
            const runingIndex = this.table.runingQueue.findIndex(v => v === current.uuid);
            if (item.status !== 'importing' && runingIndex >= 0) {
              this.table.runingQueue.splice(runingIndex, 1);
            }
          }
        });
      });
      this.table.statistics = this.handleCountData(data);
      this.tag.list.forEach((item) => {
        item.num = this.table.statistics.allCount[item.status] || 0;
      });
    },
    handleTagClick(item) {
      this.tag.active = item.status;
    },
    // 批量重试失败任务
    async handleBatchRetry() {
      // this.batchRetryLoading = true
      // 获取失败任务ID并设置任务状态
      const uuids = this.table.list
        .filter(item => item.status === 'failed')
        .map((item) => {
          item.status = 'importing';
          return item.uuid;
        });
      await this.handleImportConfig(uuids);
      this.table.runingQueue.push(...uuids);
      // this.batchRetryLoading = false
    },
    async handleRetry(uuid) {
      const index = this.table.list.findIndex(item => item.uuid === uuid);
      if (index > -1) {
        this.table.list[index].status = 'importing';
        await this.handleImportConfig([uuid]);
        // 将运行的任务加入队列中
        this.table.runingQueue.push(uuid);
      }
    },
    handleClickCollapse() {
      this.$nextTick().then(() => {
        this.collapse.activeName.forEach((item) => {
          // 首次展开默认全选
          if (!this.table.firstCheckedAll.includes(item) && this.$refs[item] && this.$refs[item].length === 1) {
            this.$refs[item][0].toggleAllSelection();
            this.table.firstCheckedAll.push(item);
          }
        });
      });
    },
    handleItemSelectable(row) {
      // 只有成功的item支持勾选
      return row.status === 'success';
    },
    // 处理底部按钮组是否悬浮
    handleResize() {
      if (!this.$el.parentElement) return;
      this.isScroll = this.$el.scrollHeight > this.$el.parentElement.clientHeight;
    },
    getItemTitle(item) {
      if (this.table.statistics[item.name]?.total) {
        const { total } = this.table.statistics[item.name];
        return `${item.title}（${this.id ? this.$t('共 {0} 个', [total]) : this.$t('已选{count}个', { count: total })}）`;
      }
      return `${item.title}`;
    },
    handleSelectChange(selection, row) {
      const index = this.table.list.findIndex(item => item.uuid === row.uuid);
      if (index > -1) {
        this.table.list[index].checked = selection.findIndex(item => item.uuid === row.uuid) > -1;
      }
    },
    handleSelectAll(selection, name) {
      this.table.list.forEach((item) => {
        if (item.type === name && item.status === 'success') {
          item.checked = !(selection.length === 0);
        }
      });
    },
    async handleImportClick() {
      if (!this.id) {
        const uuids = this.table.list
          .filter(item => item.checked && item.type !== 'bkmonitor.models.fta.plugin')
          .map(item => item.uuid);
        this.handleImportConfig({ uuids, historyId: this.table.taskId });
        await this.handleInitDetailConfigData();
        this.historyId = this.table.taskId;
      } else {
        this.$bkInfo({
          title: this.$t('覆盖已有监控目标？'),
          subTitle: this.$t('导入的配置有些已经存在监控目标，重新设置会覆盖原来的监控目标，确认覆盖请继续！'),
          okText: this.$t('继续'),
          cancelText: this.$t('取消'),
          confirmFn: () => {
            this.$router.push({
              name: 'import-configuration-target',
              params: {
                objectType: 'SERVICE'
              }
            });
          }
        });
      }
    },
    handleImportCancel() {
      if (this.id) {
        this.$bkInfo({
          title: this.$t('暂不添加监控目标？'),
          subTitle: this.$t('导入的采集配置和策略配置处于停用状态，需到列表页单独设置后才可以使用！'),
          okText: this.$t('确定'),
          cancelText: this.$t('取消'),
          confirmFn: () => {
            this.$router.push({ name: 'export-import' });
          }
        });
      } else {
        this.$router.back();
      }
    },
    handleMouseOver(e) {
      if (!this.popoverInstance) {
        this.popoverInstance = this.$bkPopover(e.target, {
          content: this.$t('监控对象不一致，无法添加统一监控目标'),
          arrow: true,
          lazy: false,
          theme: 'add-target'
        });
      } else {
        this.popoverInstance.popperInstance.reference = e.target;
        this.popoverInstance.reference = e.target;
        this.popoverInstance.setContent('监控对象不一致，无法添加统一监控目标');
        this.popoverInstance.popperInstance.update();
      }
      this.popoverInstance.show(100);
    },
    handleMouseLeave() {
      this.popoverInstance?.hide(0);
      this.popoverInstance?.destroy();
      this.popoverInstance = null;
    },
    renderHeader(h) {
      if (this.id || this.historyId) return this.$t('任务状态');

      return h(
        'div',
        {
          class: 'render-header'
        },
        [
          this.table.filterStatusName,
          h('i', {
            class: 'bk-icon icon-angle-down header-icon'
          }),
          h(
            bkSelect,
            {
              props: {
                multiple: true
              },
              on: {
                selected: this.handleHeaderStatusChange
              }
            },
            [
              h(bkOption, {
                props: {
                  id: 'failed',
                  name: this.$t('检测失败')
                }
              }),
              h(bkOption, {
                props: {
                  id: 'success',
                  name: this.$t('检测成功')
                }
              })
            ]
          )
        ]
      );
    },
    handleHeaderStatusChange(value) {
      if (value.length === 1) {
        const [first] = value;
        this.tag.active = first;
        // this.table.filterStatusName = options[0].name
      } else {
        this.table.filterStatusName = this.$t('任务状态');
        this.tag.active = 'total';
      }
    }
  }
};
</script>
<style lang="scss" scoped>
@import '../../../theme/index';

$statusColors: #94f5a4 #fd9c9c #3a84ff;
$statusBorderColors: #2dcb56 #ea3636 #3a84ff;
$collapseHeaderBackground: #f0f1f5;
$whiteColor: #fff;
$directionIconColor: #313238;
$markBackground: #caddff;

@mixin layout-flex($flexDirection: row, $alignItems: stretch, $justifyContent: flex-start) {
  display: flex;
  flex-direction: $flexDirection;
  align-items: $alignItems;
  justify-content: $justifyContent;
}

@mixin icon-direction($size: 6px) {
  display: inline-block;
  width: 0;
  height: 0;
  border: $size solid transparent;
}

@mixin button-fixed {
  position: fixed;
  bottom: 11px;
  z-index: 2;
}

@mixin collapse-item-right($colorIndex) {
  font-weight: bold;
  color: nth($statusBorderColors, $colorIndex);
}

@mixin col-row-status($i: 1) {
  width: 8px;
  height: 8px;
  margin-right: 10px;
  background: nth($statusColors, $i);
  border: 1px solid nth($statusBorderColors, $i);
  border-radius: 50%;
}

.import-config {
  min-height: 100%;

  .bk-button-icon-loading::before {
    content: '';
  }

  .bk-collapse-item {
    &-header {
      position: relative;
      padding: 0 20px;
      font-size: 12px;
      background: $collapseHeaderBackground;
      border: 1px solid $defaultBorderColor;
      border-radius: 2px 2px 0px 0px;

      @include layout-flex(row, center, space-between);

      .fr {
        display: none;
      }

      &:hover {
        color: $defaultFontColor;
      }
    }

    &-content {
      padding: 0;
    }
  }

  .bk-table {
    border-top: 0;

    .is-first .cell {
      padding-right: 0;
      padding-left: 20px;
    }

    .is-left:not(.is-first) .cell {
      padding-left: 10px;
    }
  }

  &-tag {
    margin-bottom: 10px;

    .config-tag {
      display: flex;
    }
  }

  &-content {
    .collapse-item {
      &:not(:first-child) {
        margin-top: 10px;
      }

      &-left {
        @include layout-flex(row, center);
      }

      :deep(&-right) {
        .total-success {
          @include collapse-item-right(1);
        }

        .total-failed {
          @include collapse-item-right(2);
        }

        .total-importing {
          @include collapse-item-right(3);
        }

        .separator {
          margin-right: 5px;
        }
      }

      &-icon {
        display: inline-block;
        transition: transform .2s ease-in-out;
      }

      &-title {
        margin-left: 6px;
        font-weight: bold;
      }

      &-mark {
        width: 45px;
        height: 22px;
        margin-left: 10px;
        line-height: 22px;
        color: $primaryFontColor;
        text-align: center;
        background: $markBackground;
        border-radius: 2px;
      }

      .icon-rotate {
        transform: rotate(90deg);
      }
    }

    .item-icon-left {
      border-left-color: $directionIconColor;

      @include icon-direction;
    }

    .item-icon-top {
      border-top-color: $directionIconColor;

      @include icon-direction;
    }

    .status-col {
      height: 20px;

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
      @include col-row-status(1);
    }

    .status-failed {
      @include col-row-status(2);
    }

    .detail-col {
      padding-right: 12px;

      @include layout-flex(row, center, space-between);
    }

    .render-header {
      @include layout-flex(row, center);

      .header-icon {
        margin-left: 6px;
      }

      .bk-select {
        position: absolute;
        right: 15px;
        left: 0;
        opacity: 0;
      }
    }
  }

  &-footer {
    padding: 11px 0;

    .footer-banner {
      position: fixed;
      right: 0;
      bottom: 0;
      z-index: 1;
      width: 100%;
      height: 54px;
      background: $whiteColor;
      box-shadow: 0px -3px 6px 0px rgba(49, 50, 56, .05);
    }

    .button1-wrap {
      display: inline-block;
    }

    .footer-button1 {
      @include button-fixed;
    }

    .footer-button2 {
      margin-left: 100px;

      @include button-fixed;
    }
  }
}
</style>
