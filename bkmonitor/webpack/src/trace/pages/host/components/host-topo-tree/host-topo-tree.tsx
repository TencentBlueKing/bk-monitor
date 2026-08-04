/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
 */

import { type PropType, defineComponent, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue';

import { Checkbox, Input, Loading } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { HostTopoTreeContext } from '../../composables/use-host-topo-tree';
import type { IHostTopoViewRow } from '../../composables/use-host-topo-tree-worker';
import type { IHostTopoHostNode } from '../../types';

import './host-topo-tree.scss';

export default defineComponent({
  name: 'HostTopoTree',
  props: {
    /** 由页面层注入的拓扑树控制器（MVC 中的 Controller） */
    context: {
      type: Object as PropType<HostTopoTreeContext>,
      required: true,
    },
  },
  emits: {
    /** 主机对比：source 为当前选中主机，target 为对比目标主机 */
    // compare: (_payload: { source: IHostTopoHostNode; target: IHostTopoHostNode }) => true,
    selectNode: (_payload: IHostTopoViewRow) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const ctx = props.context;
    const scrollRef = shallowRef<HTMLElement | null>(null);
    let resizeObserver: null | ResizeObserver = null;
    let scrollFrame = 0;

    const notifyViewport = () => {
      const element = scrollRef.value;
      if (element) {
        ctx.handleViewportChange(element.scrollTop, element.clientHeight, element);
      }
    };

    const handleScroll = () => {
      if (scrollFrame) {
        return;
      }
      scrollFrame = requestAnimationFrame(() => {
        scrollFrame = 0;
        notifyViewport();
      });
    };

    onMounted(() => {
      if (scrollRef.value) {
        resizeObserver = new ResizeObserver(notifyViewport);
        resizeObserver.observe(scrollRef.value);
      }
      notifyViewport();
    });

    onBeforeUnmount(() => {
      resizeObserver?.disconnect();
      if (scrollFrame) {
        cancelAnimationFrame(scrollFrame);
      }
    });

    watch(ctx.viewportResetKey, () => {
      if (scrollRef.value) {
        scrollRef.value.scrollTop = 0;
      }
      notifyViewport();
    });

    const handleNodeClick = (node: IHostTopoViewRow) => {
      ctx.handleSelectNode(node);
      ctx.handleExpandNode(node);
      emit('selectNode', node);
    };

    const handleToggle = (event: MouseEvent, node: IHostTopoViewRow) => {
      event.stopPropagation();
      ctx.handleExpandNode(node, !node.isExpanded);
    };

    // const handleCompare = (event: MouseEvent, target: IHostTopoHostNode) => {
    //   // 阻止冒泡，避免触发节点选中
    //   event.stopPropagation();
    //   const source = ctx.selectedNode.value;
    //   if (source && isHostNode(source)) {
    //     emit('compare', { source, target });
    //   }
    // };

    /** 渲染实例节点：名称 + 右侧主机数量 */
    const renderInstNode = (node: IHostTopoViewRow) => (
      <div class='topo-node topo-node--inst'>
        <span class='topo-node__label'>{node.name}</span>
        <span class='topo-node__count'>{node.hostCount}</span>
      </div>
    );

    /** 渲染主机节点：IP + 别名 +（条件）对比按钮 */
    const renderHostNode = (node: IHostTopoHostNode) => {
      // const showCompare = ctx.selectedIsHost.value && ctx.selectedNode.value?.id !== node.id;
      return (
        <div
          class='topo-node topo-node--host'
          v-bk-tooltips={{
            content: `IP：${node.ip}\n${t('主机名')}：${node.alias_name || node.bk_host_name}`,
            placement: 'right',
            delay: 100,
            extCls: 'host-topo-tooltips',
          }}
        >
          <span class='topo-node__ip'>{node.ip}</span>
          {node.alias_name && <span class='topo-node__alias'>{node.alias_name}</span>}
          {/* {showCompare && (
            <span
              class='topo-node__compare'
              onClick={(event: MouseEvent) => handleCompare(event, node)}
            >
              {t('对比')}
            </span>
          )} */}
        </div>
      );
    };

    const renderTreeNode = (node: IHostTopoViewRow) =>
      'bk_host_id' in node ? renderHostNode(node as IHostTopoHostNode) : renderInstNode(node);

    const renderRow = (node: IHostTopoViewRow) => {
      const isSelected = ctx.selectedIds.value.includes(node.id);
      return (
        <div
          key={node.id}
          style={{
            height: `${ctx.rowHeight}px`,
            paddingLeft: `${node.depth * 16 + 4}px`,
          }}
          class={['host-topo-tree__row', { 'is-selected': isSelected }]}
          onClick={() => handleNodeClick(node)}
        >
          {Array.from({ length: node.depth }, (_, depth) => `${depth * 16 + 12}px`).map(left => (
            <span
              key={left}
              style={{ left }}
              class='host-topo-tree__line'
            />
          ))}
          {node.hasChildren && node.isExpanded && (
            <span
              style={{ left: `${node.depth * 16 + 12}px` }}
              class='host-topo-tree__line host-topo-tree__line--children'
            />
          )}
          <span
            class={[
              'host-topo-tree__arrow',
              {
                'host-topo-tree__arrow--expanded': node.isExpanded,
                'host-topo-tree__arrow--hidden': !node.hasChildren,
              },
            ]}
            onClick={(event: MouseEvent) => handleToggle(event, node)}
          />
          {renderTreeNode(node)}
        </div>
      );
    };

    return () => (
      <div class='host-topo-tree'>
        <div class='host-topo-tree__header'>
          <div class='host-topo-tree__title'>{t('主机拓扑')}</div>
          <Input
            class='host-topo-tree__search'
            v-model={ctx.searchValue.value}
            placeholder={t('搜索 IP / 主机名 / 节点名称')}
            type='search'
            clearable
          />
          <div class='host-topo-tree__tools'>
            <Checkbox v-model={ctx.hideEmptyNode.value}>
              <span class='host-topo-tree__tools-label'>{t('隐藏无主机节点')}</span>
            </Checkbox>
            <div class='host-topo-tree__tools-icons'>
              <i
                class='icon-monitor icon-shouqi3 host-topo-tree__tools-icon'
                v-bk-tooltips={{ content: t('全部收起') }}
                onClick={ctx.handleCollapseAll}
              />
              <i
                class='icon-monitor icon-shuaxin host-topo-tree__tools-icon'
                v-bk-tooltips={{ content: t('刷新') }}
                onClick={ctx.handleRefresh}
              />
            </div>
          </div>
        </div>
        <Loading
          class='host-topo-tree__body'
          loading={ctx.loading.value}
        >
          <div
            ref={instance => {
              scrollRef.value = instance as HTMLElement | null;
            }}
            class='host-topo-tree__scroller'
            onScroll={handleScroll}
          >
            <div
              style={{ height: `${ctx.totalRows.value * ctx.rowHeight}px` }}
              class='host-topo-tree__spacer'
            >
              <div
                style={{
                  transform: `translate3d(0, ${ctx.visibleStart.value * ctx.rowHeight}px, 0)`,
                }}
                class='host-topo-tree__visible-rows'
              >
                {ctx.visibleRows.value.map(renderRow)}
              </div>
            </div>
            {!ctx.loading.value && ctx.totalRows.value === 0 && (
              <div class='host-topo-tree__empty'>{t('暂无数据')}</div>
            )}
          </div>
        </Loading>
      </div>
    );
  },
});
