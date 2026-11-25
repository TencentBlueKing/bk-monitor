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
  <div class="container-status-container">
    <div class="nav-section">
      <div class="nav-btn-box">
        <button
          v-for="item in navBtnList"
          :key="item.id"
          type="button"
          class="nav-btn"
          :aria-pressed="item.id === navActive"
          @click="handleClickNav(item.id)"
        >
          <span
            v-if="item.id !== 'all'"
            aria-hidden="true"
            class="container-status-icon"
          >
            <span :class="[isHaveRunning(item) ? 'container-status-spinner' : 'nav-icon', colorClass[item.id]]" />
          </span>
          <span>{{ statusNameList[item.id] }} {{ item.listNum }}</span>
        </button>
      </div>
      <t-button @click.stop="issuedRetry()">
        {{ $t('失败批量重试') }}
      </t-button>
    </div>
    <div v-if="!isLoading && !renderTitleList.length" class="bklog-table-empty-region">
      <EmptyStatus :empty-type="listFailed ? '500' : 'empty'" @operation="getContainerList()" />
    </div>
    <div v-else class="table-section">
      <div
        v-for="(renderItem, renderIndex) in renderTitleList"
        :key="renderItem.collector_config_id"
        class="table-item"
      >
        <button
          type="button"
          :aria-expanded="renderItem.isShowTable"
          :class="`table-title ${renderItem.isShowTable ? '' : 'close-table'}`"
          @click="handleClickTitle(renderIndex, renderItem.isShowTable)"
        >
          <span class="bk-icon icon-down-shape" aria-hidden="true"></span>
          <span>{{ renderItem.collector_config_name }}</span>
        </button>
        <div v-show="renderItem.isShowTable" class="table-main">
          <bk-table
            :data="renderItem[navActive]"
            size="small"
          >
            <bk-table-column
              width="80"
              label="id"
              prop="container_collector_config_id"
            ></bk-table-column>
            <bk-table-column
              :label="$t('名称')"
              prop="name"
            ></bk-table-column>
            <bk-table-column
              native-cell-slot
              :label="$t('状态')"
            >
              <template #default="{ row }">
                <div class="container-row-status">
                  <span
                    aria-hidden="true"
                    class="container-status-icon"
                  >
                    <span :class="[row.status === 'running' ? 'container-status-spinner' : 'nav-icon', colorClass[row.status]]" />
                  </span>
                  <span>{{ statusNameList[row.status] }}</span>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('详情')"
              prop="message"
            ></bk-table-column>
            <bk-table-column
              native-cell-slot
              width="80"
            >
              <template #default="{ row }">
                <a
                  v-if="row.status === 'failed'"
                  class="retry"
                  href="javascript: ;"
                  @click.stop="issuedRetry('alone', renderItem, row)"
                >
                  {{ $t('重试') }}
                </a>
              </template>
            </bk-table-column>
            <template #empty>
              <div class="bklog-table-empty-region">
                <EmptyStatus v-if="!isLoading" />
              </div>
            </template>
          </bk-table>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import { mapState as mapPiniaState } from 'pinia';
import { useCollectionStore } from '@/app/state/domains/collection-store';
import { ServicesInstance } from '@/platform/services';
import EmptyStatus from '@/shared/ui/empty-status/index.vue';



  export default {
    components: { EmptyStatus },
  emits: ["update:is-loading","update:isLoading"],

    props: {
      isLoading: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        listFailed: false,
        navActive: 'all', // 当前活跃按钮
        navBtnList: [
          // 按钮列表
          {
            id: 'all',
            listNum: 0,
          },
          {
            id: 'success',
            listNum: 0,
          },
          {
            id: 'failed',
            listNum: 0,
          },
          {
            id: 'running',
            listNum: 0,
          },
        ],
        colorClass: {
          // 成功失败类名
          success: 'circle-green',
          failed: 'circle-red',
        },
        statusNameList: {
          // 状态中文名
          all: this.$t('全部'),
          success: this.$t('正常'),
          failed: this.$t('失败'),
          running: this.$t('执行中'),
        },
        timer: null,
        renderTitleList: [], // 当前活跃的目标
        curTaskIdStr: '',
        allFailedIDList: [], // 所有状态为失败的config_id
      };
    },
    computed: {
      ...mapPiniaState(useCollectionStore, ['curCollect']),
      hasRunning() {
        // 是否还有执行中的状态
        return this.navBtnList[3].listNum;
      },
    },
    created() {
      this.curTaskIdStr = [...new Set([...this.curCollect.task_id_list])].join(',');
    },
    mounted() {
      this.getContainerList();
      this.pollingStatus();
    },
    beforeUnmount() {
      clearInterval(this.timer);
    },
    methods: {
      handleClickTitle(index, isClose) {
        this.renderTitleList[index].isShowTable = !isClose;
      },
      handleClickNav(activeID) {
        this.navActive = activeID;
      },
      /**
       * @desc: 轮询状态
       */
      pollingStatus() {
        clearInterval(this.timer);
        this.timer = setInterval(() => {
          this.getContainerList('polling');
        }, 5000);
      },
      /**
       * @desc: 容器日志list，与轮询共用
       * @param { String } isPolling 是否是轮询状态
       */
      getContainerList(isPolling = '') {
        const isRefresh = isPolling !== 'polling';
        if (isRefresh) {
          this.listFailed = false;
          this.$emit('update:is-loading', true);
        }
        const params = { collector_config_id: this.curCollect.collector_config_id };
        return ServicesInstance.collect.getIssuedClusterList({
            params,
            query: { task_id_list: this.curTaskIdStr },
          })
          .then(res => {
            const data = structuredClone(res.data.contents) || [];
            this.listFailed = false;
            this.allFailedIDList = [];
            this.navBtnList.forEach(item => (item.listNum = 0));
            const expandedByCollector = new Map(
              this.renderTitleList.map(item => [item.collector_config_id, item.isShowTable]),
            );
            this.renderTitleList = data.reduce((pre, cur) => {
              cur.isShowTable = expandedByCollector.get(cur.collector_config_id) ?? true;
              this.navBtnList.forEach(item => (cur[item.id] = []));
              if (cur.child.length) {
                cur.all = cur.child;
                for (const childItem of cur.child) {
                  childItem.status = childItem.status === 'PENDING' ? 'running' : childItem.status.toLowerCase();
                  childItem.status === 'failed' && this.allFailedIDList.push(childItem.container_collector_config_id);
                  cur[childItem.status].push(childItem);
                }
                delete cur.child;
              }
              this.navBtnList.forEach(item => (item.listNum += cur[item.id].length));
              pre.push(cur);
              return pre;
            }, []);
          })
          .catch(err => {
            if (isRefresh) this.listFailed = true;
            console.warn(err);
          })
          .finally(() => {
            if (isRefresh) this.$emit('update:is-loading', false);
            if (isPolling === 'polling' && !this.hasRunning) clearInterval(this.timer);
          });
      },
      issuedRetry(alone = '', renderItem, row) {
        const retrySubmitList = alone ? [row.container_collector_config_id] : this.allFailedIDList;
        // ID列表为空或者全局失败数为0时不请求
        if (!retrySubmitList.length || !this.navBtnList[2].listNum) return;
        if (row) {
          row.status = 'running'; // 单选 单独变成running状态
          // 失败-1 执行中+1
          renderItem.running.push(row);
          const renderIndex = renderItem.failed.findIndex(item => item.name === row.name);
          renderItem.failed.splice(renderIndex, 1);
          this.navBtnList[3].listNum += 1;
          this.navBtnList[2].listNum -= 1;
        } else {
          // 批量重试 清空失败 将所有的失败添加到执行中
          this.renderTitleList.forEach(tableItem => {
            tableItem.all.forEach(item => item.status === 'failed' && (item.status = 'running'));
            tableItem.failed.forEach(item => (item.status = 'running'));
            tableItem.running.push(...tableItem.failed);
            tableItem.failed = [];
          });
          this.navBtnList[3].listNum = this.navBtnList[3].listNum + this.navBtnList[2].listNum;
          this.navBtnList[2].listNum = 0;
        }
        ServicesInstance.source.retryList({
            params: {
              collector_config_id: this.$route.params.collectorId,
            },
            data: {
              instance_id_list: retrySubmitList,
            },
          })
          .then(() => {
            this.pollingStatus();
          })
          .catch(e => {
            console.warn(e);
          });
      },
      /**
       * @desc: 是否有重试执行中的采集状态
       * @param {Object} item
       */
      isHaveRunning(item) {
        return item.id === 'running' && item.listNum !== 0;
      },
    },
  };
</script>
<style lang="scss">
@use '@/shared/styles/mixins/flex.scss' as *;
@use '@/shared/ui/loading/status-spinner' as *;
  .container-status-container {
    .nav-section {
      flex-wrap: wrap;
      gap: var(--bklog-space-8);
      margin-block-end: var(--bklog-space-12);

      @include flex-justify(space-between);

      .nav-btn-box {
        box-sizing: border-box;
        align-items: center;
        min-width: min(327px, 100%);
        max-width: 100%;
        min-height: var(--bklog-tab-height);
        overflow-x: auto;
        padding: 5px 4px;
        font-size: 14px;
        background: var(--bklog-surface-component, var(--td-bg-color-component));
        border-radius: var(--bklog-standard-control-radius);

        @include flex-justify(space-between);

        .nav-btn {
          position: relative;
          display: flex;
          flex: none;
          white-space: nowrap;
          gap: var(--bklog-space-4);
          align-items: center;
          padding: var(--bklog-space-4) var(--bklog-space-16);
          font: inherit;
          color: var(--bklog-standard-control-text, var(--td-text-color-secondary));
          cursor: pointer;
          background: transparent;
          border: 0;
          border-radius: var(--bklog-standard-control-radius);

          &:not(:last-child)::after {
            position: absolute;
            top: 3px;
            right: -8px;
            color: var(--bklog-panel-divider, var(--td-component-stroke));
            content: '|';
          }

          &:not(:first-child) {
            margin-left: 12px;
          }

          &:hover {
            background: var(--bklog-surface, var(--td-bg-color-container));
          }

          &:focus-visible {
            outline: var(--bklog-border-width) solid var(--td-brand-color);
            outline-offset: calc(-1 * var(--bklog-border-width));
          }

          &[aria-pressed="true"] {
            color: var(--bklog-brand-primary, var(--td-brand-color));
            background: var(--bklog-surface, var(--td-bg-color-container));
          }
        }
      }
    }

    .container-status-icon {
      @include collection-status-icon-slot();
    }

    .nav-icon {
      @include collection-status-dot();

      &.circle-green {
        @include collection-status-dot-color(var(--bklog-status-success, var(--td-success-color)), var(--bklog-status-success-ring, var(--td-success-color-light)));
      }

      &.circle-red {
        @include collection-status-dot-color(var(--bklog-status-error, var(--td-error-color)), var(--bklog-status-error-ring, var(--td-error-color-light)));
      }
    }

    .container-row-status {
      display: flex;
      gap: var(--bklog-space-4);
      align-items: center;
    }

    .container-status-spinner {
      display: inline-block;
      flex: none;
      width: 14px;
      height: 14px;
      vertical-align: middle;

      @include status-spinner();
      @include status-spinner-segments();
    }

    .table-section {
      .table-item + .table-item {
        margin-block-start: var(--bklog-space-12);
      }

      .table-item {

        .table-title {
          box-sizing: border-box;
          display: flex;
          align-items: center;
          gap: var(--bklog-space-4);
          width: 100%;
          min-height: var(--bklog-table-header-medium);
          padding: 0 var(--bklog-space-24);
          font: inherit;
          font-size: var(--bklog-font-body);
          color: var(--bklog-standard-control-text, var(--td-text-color-secondary));
          text-align: start;
          cursor: pointer;
          background: var(--bklog-surface-component, var(--td-bg-color-component));
          border: var(--bklog-border-width) solid var(--bklog-panel-divider, var(--td-component-stroke));
          border-bottom: none;

          &:focus-visible {
            outline: var(--bklog-border-width) solid var(--td-brand-color);
            outline-offset: calc(-2 * var(--bklog-border-width));
          }

          > span {
            &:first-child {
              font-size: 14px;
            }

            &:nth-child(2) {
              font-weight: var(--bklog-table-header-font-weight);
              color: var(--bklog-standard-control-text, var(--td-text-color-secondary));
            }
          }

          .icon-down-shape {
            display: inline-block;
            transform: translateY(-1px);
          }

          &.close-table {
            border-bottom: var(--bklog-border-width) solid var(--bklog-panel-divider, var(--td-component-stroke));

            .icon-down-shape {
              transform: rotateZ(-90deg) translateX(1px);
            }
          }
        }

        .retry {
          color: var(--bklog-brand-primary, var(--td-brand-color));
        }
      }
    }
  }
</style>
