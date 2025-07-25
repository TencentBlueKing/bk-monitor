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
  <div
    v-bkloading="{ isLoading: reload }"
    class="host-list"
    data-tag="resizeTarget"
    :style="{ width: drag.width + 'px', 'flex-basis': drag.width + 'px' }"
  >
    <div
      class="resize-line"
      @mousedown="handleMouseDown"
    />
    <div class="host-list-title">
      <span>{{ $t('主机列表') }}</span>
      <i
        class="icon-monitor icon-double-up"
        @click="handleTogglePanel"
      />
    </div>
    <div class="host-list-content">
      <div class="content-top">
        <bk-input
          v-model="keyword"
          @change="handleSearch"
        />
        <span
          :class="['content-top-refresh', { loading: reload }]"
          @click="handleReloadList"
        >
          <i class="icon-monitor icon-mc-alarm-recovered" />
        </span>
      </div>
      <bk-alert
        v-if="isTargetCompare"
        type="info"
        class="select-target-tips"
        closable
        :show-icon="false"
      >
        <div
          slot="title"
          class="tips-main"
        >
          <i class="icon-monitor icon-tips" />
          <span class="text">{{ $t('选择目标进行对比') }}</span>
        </div>
      </bk-alert>
      <div class="content-bottom">
        <bk-big-tree
          v-if="hostTopoTreeList && hostTopoTreeList.length"
          ref="bkBigTree"
          :class="['big-tree', { 'selectable-tree': !enableCmdbLevel }]"
          :default-expanded-nodes="defaultExpandedID"
          :default-selected-node="defaultExpandedID[0]"
          :filter-method="filterMethod"
          :data="hostTopoTreeList"
          :height="treeHeight"
          :selectable="enableCmdbLevel"
          :expand-on-click="false"
        >
          <template #empty>
            <div>empty</div>
          </template>
          <template #default="{ data }">
            <div
              :class="[
                'bk-tree-node',
                {
                  active:
                    `${data.ip}-${data.bk_cloud_id}` === curNode.id ||
                    (enableCmdbLevel && `${data.bk_inst_id}-${data.bk_obj_id}` === curNode.id),
                  'checked-target': isTargetCompare && checkedTarget.includes(`${data.bk_cloud_id}-${data.ip}`),
                },
              ]"
              @click="handleItemClick(data)"
            >
              <span
                class="node-content"
                style="padding-right: 5px"
              >
                <span
                  v-if="data.status !== undefined"
                  :class="['item-status', `status-${statusMap[data.status].status}`]"
                />
                <span>{{ data.ip || data.bk_inst_name }}</span>
                <span
                  v-if="data.bkHostName"
                  class="host-name"
                  >({{ data.bkHostName }})</span
                >
                <span
                  v-if="data.ip && isTargetCompare"
                  class="add-compared"
                >
                  <i
                    v-if="checkedTarget.includes(`${data.bk_cloud_id}-${data.ip}`)"
                    class="icon-monitor icon-mc-check-small"
                  />
                  <span
                    v-else
                    class="add-compared-btn"
                    @click.stop="handleAddCompareTarget(data)"
                    >{{ $t('对比') }}</span
                  >
                </span>
              </span>
            </div>
          </template>
        </bk-big-tree>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { deepClone } from 'monitor-common/utils/utils';
import { debounce } from 'throttle-debounce';

import PerformanceModule, { type ICurNode } from '../../../store/modules/performance';

import type { IQueryOption } from '../performance-type';

@Component({ name: 'host-list' })
export default class HostList extends Vue {
  @Ref('hostList') refHostList: any;
  @Ref('bkBigTree') readonly bkBigTreeRef: any;

  @Prop({ default: '', type: Object }) readonly curNode: ICurNode;
  @Prop({ default: () => ({}), type: Object }) compareValue: IQueryOption;
  // 是否显示面板
  @Model('visible-change', { default: true }) readonly visible: boolean;

  private treeHeight = 700;
  // 重新加载
  private reload = false;
  private itemHeight = 32;
  private statusMap = {
    '-1': {
      name: window.i18n.t('未知'),
      status: '3',
    },
    0: {
      name: window.i18n.t('正常'),
      status: '1',
    },
    1: {
      name: window.i18n.t('离线'),
      status: '1',
    },
    2: {
      name: window.i18n.t('无Agent'),
      status: '2',
    },
    3: {
      name: window.i18n.t('无数据上报'),
      status: '3',
    },
  };
  private searchData = [
    {
      name: '集群',
      id: 'cluster',
      children: [
        {
          name: '蓝鲸',
          id: 'bkmonitor',
        },
      ],
    },
    {
      name: '模块',
      id: 'module',
      children: [
        {
          name: 'paas平台',
          id: 'pass',
        },
      ],
    },
    {
      name: '操作系统',
      id: 'system',
      children: [
        {
          name: '蓝鲸',
          id: 'bkmonitor',
        },
      ],
    },
  ];
  private keyword = '';
  private drag = {
    width: 280,
    minWidth: 100,
    maxWidth: 500,
    defaultWidth: 280,
    dragDown: false,
  };
  private handleSearch = null;
  private handleResizeTreeDebounce = null;
  @Watch('curNode', { immediate: true, deep: true })
  onActiveChange() {
    this.keyword = '';
  }
  @Watch('visible', { immediate: true })
  visibleChange(v) {
    if (v) {
      !this.drag.dragDown && (this.drag.width = this.drag.defaultWidth);
    }
  }

  get enableCmdbLevel() {
    return this.$store.getters.enable_cmdb_level;
  }
  get hostList() {
    return Object.freeze(PerformanceModule.filterHostList);
  }
  get hostTopoTreeList() {
    if (!this.hostList.length) return [];
    const resList = deepClone(PerformanceModule.filterHostTopoTreeList);
    const hostMap = new Map();

    for (const item of this.hostList) {
      hostMap.set(`${item.bk_host_innerip}-${item.bk_cloud_id}`, item);
    }
    const fn = (list): any => {
      if (list?.length) {
        for (const item of list) {
          if (item.ip) {
            // const target = this.hostList.find((tar) => {
            //   const a = `${item.ip}-${item.bk_cloud_id}`
            //   const b = `${tar.bk_host_innerip}-${tar.bk_cloud_id}`
            //   return  a === b
            // })
            const target = hostMap.get(`${item.ip}-${item.bk_cloud_id}`);
            item.status = target.status;
            item.bkHostName = target.bk_host_name;
          } else if (item.children?.length) {
            fn(item.children);
          }
        }
      }
    };
    fn(resList);
    return Object.freeze(resList);
  }
  get defaultExpandedID() {
    const fn = (list, targetName): any => {
      if (list?.length) {
        for (const item of list) {
          const sourceId =
            this.curNode.type === 'host' ? `${item.ip}-${item.bk_cloud_id}` : `${item.bk_inst_id}-${item.bk_obj_id}`;
          if (sourceId === targetName) {
            return item;
          }
          if (item.children?.length) {
            const res = fn(item.children, targetName);
            if (res) return res;
          }
        }
      }
    };
    const res = fn(this.hostTopoTreeList, this.curNode.id);
    const data = res ? [res.id] : [];
    if (this.bkBigTreeRef) {
      this.bkBigTreeRef.setSelected(data[0]);
      this.bkBigTreeRef.setExpanded(data);
    }
    return data;
  }
  /**
   * @description: 是否在目标对比
   */
  get isTargetCompare() {
    return this.compareValue.compare.type === 'target';
  }
  /**
   * @description: 选中的目标对比
   */
  get checkedTarget() {
    return this.isTargetCompare ? ((this.compareValue.compare.value || []) as string[]) : [];
  }

  created() {
    PerformanceModule.getTopoTree({
      instance_type: 'host',
      remove_empty_nodes: false,
    });
    this.handleSearch = debounce(300, v => {
      //   PerformanceModule.setKeyWord(v)
      this.bkBigTreeRef?.filter(v);
    });
  }
  mounted() {
    this.handleResizeTreeDebounce = debounce(300, this.handleResizeTree);
  }
  activated() {
    this.refHostList?.resize();
  }

  handleItemClick(data) {
    const curNode: ICurNode = {
      type: 'host',
      id: '',
    };
    if (!data.ip) {
      curNode.type = 'node';
      curNode.id = `${data.bk_inst_id}-${data.bk_obj_id}`;
      curNode.bkInstId = data.bk_inst_id;
      curNode.bkObjId = data.bk_obj_id;
    } else {
      curNode.type = 'host';
      curNode.id = `${data.ip}-${data.bk_cloud_id}`;
      curNode.ip = data.ip;
      curNode.cloudId = data.bk_cloud_id;
    }
    // 功能开关
    if (!this.enableCmdbLevel && curNode.type === 'node') return;

    this.handleNodeChange(curNode);
  }
  @Emit('node-change')
  handleNodeChange(data: ICurNode) {
    return data;
  }

  // 显示和隐藏面板
  @Emit('visible-change')
  handleTogglePanel() {
    return !this.visible;
  }

  @Emit('reload')
  async handleReloadList() {
    this.reload = true;
    this.keyword = '';
    await PerformanceModule.getHostPerformance();
    this.reload = false;
  }

  @Emit('add-target')
  handleAddCompareTarget(data: any): string {
    return `${data.bk_cloud_id}-${data.ip}`;
  }

  filterMethod(keyword: string, node: any): boolean {
    const { data } = node;
    return data.ip && (data.ip + data.bk_host_name).indexOf(keyword) > -1;
  }

  // 更新树形组件宽度
  handleResizeTree() {
    this.bkBigTreeRef?.resize();
  }

  // drag触发
  handleMouseDown(e) {
    let { target } = e;
    while (target && target.dataset.tag !== 'resizeTarget') {
      target = target.parentNode;
    }
    this.drag.dragDown = true;
    const rect = target.getBoundingClientRect();
    document.onselectstart = () => false;
    document.ondragstart = () => false;
    const handleMouseMove = event => {
      if (event.clientX - rect.left < this.drag.minWidth) {
        this.drag.width = 0;
        if (this.visible) this.handleTogglePanel();
      } else {
        this.drag.width = Math.min(Math.max(this.drag.minWidth, event.clientX - rect.left), this.drag.maxWidth);
        if (!this.visible) this.handleTogglePanel();
      }
      this.handleResizeTreeDebounce();
    };
    const handleMouseUp = () => {
      this.drag.dragDown = false;
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.onselectstart = null;
      document.ondragstart = null;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }
}
</script>
<style lang="scss" scoped>
$statusBorderColors: #2dcb56 #c4c6cc #ea3636;
$statusColors: #94f5a4 #f0f1f5 #fd9c9c;

@keyframes rotate {
  0% {
    transform: rotate(0deg);
  }

  50% {
    transform: rotate(180deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.host-list {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
  border-right: 1px solid #f0f1f5;

  .resize-line {
    right: 0;
    cursor: col-resize;
    background: none;
  }

  &-title {
    display: flex;
    flex: 0 0 42px;
    align-items: center;
    justify-content: space-between;
    padding: 0 8px 0 20px;
    border-bottom: 1px solid #f0f1f5;

    i {
      font-size: 24px;
      color: #979ba5;
      cursor: pointer;
      transform: rotate(-90deg);
    }
  }

  &-content {
    height: calc(100% - 42px);
    padding: 16px 20px 0 20px;

    .content-top {
      display: flex;

      &-search {
        flex: 1;
      }

      &-refresh {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        margin-left: 2px;
        font-size: 16px;
        cursor: pointer;
        border: 1px solid #c4c6cc;

        i {
          width: 16px;
          height: 16px;
        }

        &.loading i {
          animation: rotate 2s linear infinite;
        }
      }
    }

    .select-target-tips {
      margin-top: 4px;

      .tips-main {
        font-size: 0;

        .icon-tips {
          margin-right: 8px;
          font-size: 16px;
          color: #3a84ff;
          vertical-align: middle;
        }

        .text {
          font-size: 12px;
          vertical-align: middle;
        }
      }
    }

    .content-bottom {
      height: calc(100% - 64px);
      margin-top: 16px;

      :deep(.big-tree) {
        /* stylelint-disable-next-line declaration-no-important */
        height: 100% !important;
      }

      .item-status {
        display: inline-block;
        width: 6px;
        min-width: 6px;
        height: 6px;
        border: 1px solid;
        border-radius: 50%;
      }

      &-item {
        display: flex;
        align-items: center;
        height: 32px;
        padding-left: 10px;
        cursor: pointer;

        &:hover {
          background: #f5f6fa;
        }

        .item-name {
          margin-left: 2px;
          color: #c4c6cc;
        }

        &.active {
          color: #3a84ff;
          background: #e1ecff;

          .item-name {
            color: #3a84ff;
          }
        }
      }

      /* stylelint-disable-next-line no-duplicate-selectors */
      :deep(.big-tree) {
        width: max-content;
        min-width: 100%;

        .bk-big-tree-node {
          padding-left: calc((var(--level) * 16px) + 8px);

          .bk-tree-node {
            .node-content {
              position: relative;

              .add-compared {
                position: absolute;
                top: 0;
                right: 0;
                height: 32px;
                padding-right: 8px;
                padding-left: 8px;

                .add-compared-btn {
                  display: none;
                }
              }
            }

            &.checked-target {
              color: #979ba5;
              background-color: #f5f7fa;

              .node-content {
                .add-compared {
                  background-color: #f5f7fa;

                  .icon-mc-check-small {
                    font-size: 20px;
                    color: #979ba5;
                  }
                }
              }
            }
          }

          &:hover {
            color: #3a84ff;
            background-color: #e1ecff;

            .bk-tree-node {
              background-color: #e1ecff;

              .node-content {
                .add-compared {
                  background-color: #e1ecff;

                  .add-compared-btn {
                    display: initial;
                  }
                }
              }
            }
          }

          &.is-selected {
            .bk-tree-node {
              background-color: #e1ecff;

              .node-content {
                .add-compared {
                  .add-compared-btn {
                    display: none;
                  }
                }
              }
            }
          }

          &.is-leaf {
            padding-left: 0;
            cursor: default;

            .bk-tree-node {
              height: 32px;
              padding-left: calc((var(--level) * 16px) + 8px + 20px);

              @for $i from 1 through length($statusColors) {
                .status-#{$i} {
                  /* stylelint-disable-next-line function-no-unknown */
                  background: nth($statusColors, $i);

                  /* stylelint-disable-next-line function-no-unknown */
                  border: 1px solid nth($statusBorderColors, $i);
                }
              }

              .node-content {
                display: flex;
                align-items: center;
                cursor: pointer;

                .item-status {
                  margin-right: 10px;
                }

                .host-name {
                  color: #c4c6cc;
                }
              }
            }
          }
        }
      }

      :deep(.selectable-tree) {
        .bk-big-tree-node.is-leaf {
          padding-left: 0;

          .active {
            width: 100%;
            color: #3a84ff;
            background-color: #e1ecff;
          }
        }
      }

      :deep(.bk-scroll-home) {
        .bk-min-nav-slide {
          width: 5px;
          border-radius: 5px;
        }
      }
    }
  }
}
</style>
