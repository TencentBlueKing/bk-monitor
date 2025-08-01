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
    class="import-config"
  >
    <!--按钮组（统计信息）-->
    <section class="import-config-tag fix-same-code">
      <div class="config-tag fix-same-code">
        <div class="bk-button-group fix-same-code">
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
          class="ml10 fix-same-code"
          :disabled="disabledBatchRetryBtn"
          hover-theme="primary"
          @click="handleBatchRetry"
        >
          <span class="icon-monitor icon-mc-retry fix-same-code" /> {{ $t('批量重试') }}
        </bk-button>
      </div>
    </section>
    <!--折叠内容-->
    <section
      ref="collapse"
      class="import-config-content"
      :style="{ marginBottom: isScroll ? '34px' : '' }"
    >
      <bk-collapse v-model="collapse.activeName">
        <bk-collapse-item
          v-for="item in collapse.list"
          v-show="tableData(item.name).length !== 0"
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
              <span class="collapse-item-title">{{ countData(item) }}</span>
              <span
                v-if="item.markName"
                class="collapse-item-mark"
                >{{ item.markName }}</span
              >
            </div>
            <!--右侧状态-->
            <div
              v-show="table.statistics && table.statistics[item.name]"
              class="collapse-item-right"
            >
              <!-- eslint-disable-next-line vue/no-v-html -->
              <span>
                <template v-for="(val, key) in statusMap">
                  <i18n
                    v-if="
                      table.statistics[item.name] &&
                      table.statistics[item.name][key] &&
                      (tag.active === 'total' || tag.active === key)
                    "
                    :key="key"
                    :path="key === 'success' ? '{0}个成功' : key === 'failed' ? '{0}个失败' : '{0}个导入中'"
                  >
                    <span :class="`total-${key}`">{{ table.statistics[item.name][key] }}</span>
                  </i18n>
                </template>
              </span>
            </div>
          </template>
          <!--折叠表格-->
          <template #content>
            <bk-table
              v-show="tableData(item.name)"
              :ref="item.name"
              max-height="410"
              :data="tableData(item.name)"
            >
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
                class="fix-same-code"
                :label="$t('任务状态')"
                width="153"
              >
                <template #default="{ row }">
                  <!--运行、成功、失败状态-->
                  <div
                    v-if="statusMap[row.status]"
                    class="status-col fix-same-code"
                  >
                    <span
                      v-if="row.status === 'importing'"
                      class="status-runing fix-same-code icon-monitor icon-loading"
                    />
                    <span
                      v-else
                      :class="'status-' + row.status"
                    />
                    <span>{{ statusMap[row.status].name }}</span>
                  </div>
                  <!--未知状态-->
                  <div
                    v-else
                    class="status-col fix-same-code"
                  >
                    <span class="status-failed fix-same-code" />
                    <span> {{ $t('状态未知') }} </span>
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('详情')">
                <template #default="{ row }">
                  <div class="detail-col fix-same-code">
                    <span>{{ row.errorMsg ? row.errorMsg : '--' }}</span>
                    <!--失败重试-->
                    <bk-button
                      v-show="row.status === 'failed' && item.name !== 'bkmonitor.models.fta.plugin'"
                      ext-cls="detail-col-button"
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
    <!--空数据-->
    <section
      v-show="isShowEmpty"
      class="import-config-empty"
    >
      <content-empty
        :title="$t('无数据')"
        :sub-title="$t('筛选数据为空')"
      />
    </section>
    <!--底部按钮-->
    <section class="import-config-footer">
      <!--背景占位-->
      <div :class="{ 'footer-banner': isScroll }" />
      <!--按钮wrap 悬浮-->
      <div
        class="button1-wrap"
        @mouseover="!isRepeat && handleMouseOver($event)"
        @mouseleave="!isRepeat && handleMouseLeave($event)"
      >
        <bk-button
          theme="primary"
          class="mr10"
          :class="{ 'footer-button1': isScroll }"
          :disabled="disabledConfirmBtn"
          @click="handleImportClick"
        >
          {{ $t('前往添加统一监控目标') }}
        </bk-button>
      </div>
      <bk-button
        class="button-cancel"
        :class="{ 'footer-button2': isScroll }"
        :style="{ marginLeft: isScroll ? '182px' : '' }"
        @click="handleImportCancel"
      >
        {{ $t('暂不添加') }}
      </bk-button>
    </section>
  </article>
</template>
<script>
import { mapActions, mapGetters } from 'vuex';

import ContentEmpty from '../components/content-empty';
import mixin from './import-mixin';

export default {
  name: 'ImportConfigurationImporting',
  components: {
    ContentEmpty,
  },
  mixins: [mixin],
  props: {
    // history id
    id: {
      type: [Number, String],
      default: 0,
    },
  },
  data() {
    return {
      // 顶部按钮组
      tag: {
        list: [
          {
            name: this.$t('全部'),
            num: 0,
            status: 'total',
          },
          {
            name: this.$t('成功'),
            num: 0,
            status: 'success',
          },
          {
            name: this.$t('失败'),
            num: 0,
            status: 'failed',
          },
          {
            name: this.$t('执行中'),
            num: 0,
            status: 'importing',
          },
        ],
        active: 'total',
      },
      // 当前statusMap
      statusMap: {
        success: {
          name: this.$t('成功'),
          status: 'success',
        },
        failed: {
          name: this.$t('失败'),
          status: 'failed',
        },
        importing: {
          name: this.$t('导入中'),
          status: 'importing',
        },
      },
      // 私有表格属性（公共属性在mixin中）
      table: {
        runingQueue: [],
        timer: null,
        interval: 2000,
      },
      // 批量重试loading
      batchRetryLoading: false,
      // 悬浮提示对象
      popoverInstance: null,
      // 当前 table list 中是否都是重复监控对象（相同的监控对象可添加监控目标）
      isRepeat: false,
      // 统一监控对象名称
      targetType: '',
      // 历史ID
      historyId: this.id,
    };
  },
  computed: {
    ...mapGetters('import', ['cancelReq']),
    // 批量重试按钮禁用状态
    disabledBatchRetryBtn() {
      return (
        this.table.runingQueue.length !== 0 ||
        this.table.list.filter(item => item.status === 'failed' && item.type !== 'bkmonitor.models.fta.plugin')
          .length === 0
      );
    },
    // 统一添加监控目标按钮禁用状态
    disabledConfirmBtn() {
      // 监控对象不一致、没有成功任务、有导入任务下都禁用
      return (
        !this.isRepeat ||
        !this.table.list.some(item => item.status === 'success') ||
        this.table.list.some(item => item.status === 'importing')
      );
    },
    // 计算各个分类的表格数据
    tableData() {
      // 从list中筛选出每个表格的数据
      return type =>
        this.table.list.filter(item => {
          const isCurTag = this.tag.active === 'total' || item.status === this.tag.active;
          return item.type === type && isCurTag;
        });
    },
    // 统计表格数据
    countData() {
      return collapse => {
        const checkedCount = this.tableData(collapse.name).length;
        return `${collapse.title}（${this.$t('共 {0} 个', [checkedCount])}）`;
      };
    },
    // 是否显示空界面
    isShowEmpty() {
      return !this.table.list.filter(item => this.tag.active === 'total' || item.status === this.tag.active).length;
    },
  },
  watch: {
    'table.runingQueue': {
      handler(runingQueue) {
        if (runingQueue?.length > 0 && !this.table.timer) {
          // 开启定时任务
          this.handleRunTimer();
        } else if (!runingQueue || runingQueue.length === 0) {
          // 当且仅当运行队列为空时才能移除timer
          // 结束所有任务
          clearTimeout(this.table.timer);
          this.table.timer = null;
        }
      },
      immediate: true,
    },
    id: {
      handler(v, o) {
        if (v !== o) {
          this.historyId = v;
          this.handleInit();
        }
      },
    },
  },
  created() {
    // just do it
    this.handleInit();
  },
  activated() {
    // this.$forceUpdate() // 解决表格不能自适应问题
    this.tag.active = 'total';
    !this.loading && this.handleInit();
  },
  beforeRouteLeave(to, from, next) {
    this.table.runingQueue = [];
    next();
  },
  beforeDestroy() {
    this.table.runingQueue = [];
  },
  methods: {
    ...mapActions('import', ['handleImportConfig', 'getHistoryDetail']),
    /**
     * 初始化数据
     */
    async handleInit() {
      if (!this.historyId) return;
      this.loading = true;
      const data = await this.getHistoryDetail(this.historyId).catch(() => {
        this.loading = false;
      });
      // 表格数据
      this.table.list = data.configList.map(item => {
        item.status = item.importStatus;
        return item;
      });
      // 统计数据
      this.table.statistics = this.handleCountData(data);
      this.tag.list.forEach(item => {
        item.num = this.table.statistics.allCount[item.status] || 0;
      });
      // 检测监控目标是否统一
      this.handleDetectionTarget();
      // 刷新运行中的任务
      this.handlePushRuningTask();
      // 展开第一个有数据的项
      this.handleExpandCollapse();
      this.loading = false;
    },
    /**
     * 检测监控目标是否是同一个
     */
    handleDetectionTarget() {
      const hasRepeat = {};
      this.isRepeat = this.table.list
        .filter(item => item.type !== 'bkmonitor.models.fta.plugin' && item.status === 'success')
        .every(item => {
          if (!Object.keys(hasRepeat).length && item.targetType) {
            hasRepeat[item.targetType] = true;
            this.targetType = item.targetType;
          }
          return !!hasRepeat[item.targetType];
        });
    },
    /**
     * 运行轮询任务
     */
    async handleRunTimer() {
      const interval = cb => {
        const fn = async () => {
          if (this.table.runingQueue.length === 0) {
            clearTimeout(this.table.timer);
            this.table.timer = null;
            return;
          }
          await cb();
          this.table.timer = setTimeout(() => {
            fn();
          }, this.table.interval);
        };

        this.table.timer = setTimeout(fn, this.table.interval);
      };
      interval(async () => {
        // todo
        const data = await this.getHistoryDetail(this.historyId);
        this.handleChangeStatus(data);
      });
    },
    /**
     * 添加任务到任务队列
     */
    handlePushRuningTask() {
      const uuids = this.table.list
        .filter(item => {
          const notInclude = !this.table.runingQueue.includes(item.uuid);
          return item.status === 'importing' && notInclude;
        })
        .map(item => item.uuid);
      if (!uuids.length) return;
      this.table.runingQueue.push(...uuids);
    },
    /**
     * 处理轮询回来的数据
     * @param {Object} data
     */
    handleChangeStatus(data) {
      if (!data || !data.configList.length) return;
      this.table.list = data.configList.map(item => {
        item.status = item.importStatus;
        // 如果当前状态不为importing则移除
        if (this.table.runingQueue.includes(item.uuid) && item.status !== 'importing') {
          const runingIndex = this.table.runingQueue.findIndex(v => v === item.uuid);
          this.table.runingQueue.splice(runingIndex, 1);
        }
        return item;
      });
      this.table.statistics = this.handleCountData(data);
      this.tag.list.forEach(item => {
        item.num = this.table.statistics.allCount[item.status] || 0;
      });
      this.handleDetectionTarget();
    },
    /**
     * 按钮组点击事件
     * @param {Object} item
     */
    handleTagClick(item) {
      this.tag.active = item.status;
    },
    // 批量重试失败任务
    async handleBatchRetry() {
      // this.batchRetryLoading = true
      this.handleResetQueue();
      // 获取失败任务ID并设置任务状态（为了防止接口返回慢导致任务状态扭转卡顿）
      const uuids = this.table.list
        .filter(item => item.status === 'failed' && item.type !== 'bkmonitor.models.fta.plugin')
        .map(item => {
          item.status = 'importing';
          return item.uuid;
        });
      this.handleStatistics();
      // 发送请求改变状态
      await this.handleImportConfig({ uuids, historyId: this.historyId });
      this.handlePushRuningTask();
      // this.table.runingQueue.push(...uuids)
      // this.batchRetryLoading = false
    },
    /**
     * 单条重试
     * @param {String} uuid
     */
    async handleRetry(uuid) {
      const index = this.table.list.findIndex(item => item.uuid === uuid);
      if (index > -1) {
        this.handleResetQueue();
        this.table.list[index].status = 'importing';
        this.handleStatistics();
        await this.handleImportConfig({ uuids: [uuid], historyId: this.historyId });
        this.handlePushRuningTask();
        // 将运行的任务加入队列中
        // this.table.runingQueue.push(uuid)
      }
    },
    /**
     * 统计当前table list数据
     */
    handleStatistics() {
      const countData = {
        allCount: {
          failed: 0,
          importing: 0,
          success: 0,
          total: 0,
        },
      };
      this.table.list.forEach(item => {
        if (!countData[item.type]) {
          countData[item.type] = {
            failed: 0,
            importing: 0,
            success: 0,
            total: 0,
          };
        }
        countData.allCount.total += 1;
        countData.allCount[item.status] += 1;
        countData[item.type].total += 1;
        countData[item.type][item.status] += 1;
      });
      // 统计数据
      this.table.statistics = countData;
      this.tag.list.forEach(item => {
        item.num = this.table.statistics.allCount[item.status] || 0;
      });
    },
    // 重置任务队列
    async handleResetQueue() {
      this.table.runingQueue.splice(0, this.table.runingQueue.length);
      if (this.cancelReq) {
        // abort上一次请求，防止数据不匹配
        this.cancelReq();
      }
    },
    /**
     * 统一添加监控目标
     */
    async handleImportClick() {
      const existTarget = this.table.list.some(item => item.existTarget); // 之前是否添加过监控对象
      const { targetType } = this;
      const { historyId } = this;
      const handleGoToTarget = () => {
        this.$router.push({
          name: 'import-configuration-target',
          params: {
            targetType,
            historyId,
          },
        });
      };
      if (existTarget) {
        const h = this.$createElement;
        this.$bkInfo({
          title: this.$t('覆盖已有监控目标？'),
          subHeader: h(
            'div',
            {
              style: {
                fontSize: '12px',
                textAlign: 'center',
              },
            },
            this.$t('导入的配置有些已经存在监控目标，重新设置会覆盖原来的监控目标，确认覆盖请继续！')
          ),
          okText: this.$t('继续'),
          cancelText: this.$t('取消'),
          confirmFn: handleGoToTarget,
        });
      } else {
        handleGoToTarget();
      }
    },
    /**
     * 暂不添加按钮事件
     */
    handleImportCancel() {
      const existTarget = this.table.list.some(item => item.existTarget); // 之前是否添加过监控对象
      if (existTarget) {
        this.$router.push({ name: 'export-import' });
      } else {
        const h = this.$createElement;
        this.$bkInfo({
          title: this.$t('暂不添加监控目标？'),
          subHeader: h(
            'div',
            {
              style: {
                fontSize: '12px',
                textAlign: 'center',
              },
            },
            this.$t('导入的采集配置和策略配置处于停用状态，需到列表页单独设置后才可以使用！')
          ),
          okText: this.$t('确定'),
          cancelText: this.$t('取消'),
          confirmFn: () => {
            this.$router.push({ name: 'export-import' });
          },
        });
      }
    },
    /**
     * 鼠标悬浮提示
     */
    handleMouseOver(e) {
      if (!this.popoverInstance) {
        this.popoverInstance = this.$bkPopover(e.target, {
          theme: 'add-target',
          content: this.$t('监控对象不一致，无法添加统一监控目标'),
          lazy: false,
          arrow: true,
        });
      } else {
        this.popoverInstance.setContent('监控对象不一致，无法添加统一监控目标');
        this.popoverInstance.popperInstance.reference = e.target;
        this.popoverInstance.reference = e.target;
        this.popoverInstance.popperInstance.update();
      }
      this.popoverInstance.show(120);
    },
    handleMouseLeave() {
      this.popoverInstance?.hide(1);
      this.popoverInstance?.destroy();
      this.popoverInstance = null;
    },
  },
};
</script>
<style lang="scss" scoped>
@import 'import-common';
</style>
