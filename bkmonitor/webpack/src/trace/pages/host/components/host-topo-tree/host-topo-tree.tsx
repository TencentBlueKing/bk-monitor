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

import { type PropType, defineComponent } from 'vue';

import { Checkbox, Input, Loading, Tree } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { countHostNodes, isHostNode } from '../../utils/topo-tree';

import type { HostTopoTreeContext } from '../../composables/use-host-topo-tree';
import type { IHostTopoHostNode, IHostTopoTreeNode } from '../../types';

import './host-topo-tree.scss';

/** bk-tree 自定义节点插槽参数：节点业务数据 + 组件内置属性 */
type ITreeSlotNode = IHostTopoTreeNode & { __attr__?: { hasChildNode?: boolean; isOpen?: boolean; isRoot?: boolean } };

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
    compare: (_payload: { source: IHostTopoHostNode; target: IHostTopoHostNode }) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const ctx = props.context;

    // 点击内容：选中 + 展开 + 触发 click；不含 collapse，保证「收起只能点小三角」
    const nodeContentAction = ['selected', 'expand', 'click'];

    /** 保留展开箭头、去掉节点类型（文件夹/文件）图标 */
    const getPrefixIcon = (_item: ITreeSlotNode, renderType: string) =>
      renderType === 'node_action' ? 'default' : null;

    const handleNodeClick = (node: IHostTopoTreeNode) => {
      ctx.handleSelectNode(node);
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
    const renderInstNode = (node: ITreeSlotNode) => (
      <div class='topo-node topo-node--inst'>
        <span class='topo-node__label'>{node.name}</span>
        <span class='topo-node__count'>{countHostNodes(node)}</span>
      </div>
    );

    /** 渲染主机节点：IP + 别名 +（条件）对比按钮 */
    const renderHostNode = (node: IHostTopoHostNode) => {
      // const showCompare = ctx.selectedIsHost.value && ctx.selectedNode.value?.id !== node.id;
      return (
        <div
          class='topo-node topo-node--host'
          v-bk-tooltips={{
            content: `${t('IP')}：${node.ip}\n${t('主机名')}：${node.alias_name || node.bk_host_name}`,
            placement: 'right',
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

    const renderTreeNode = (node: ITreeSlotNode) => (isHostNode(node) ? renderHostNode(node) : renderInstNode(node));

    return () => (
      <div class='host-topo-tree'>
        <div class='host-topo-tree__header'>
          <div class='host-topo-tree__title'>{t('主机拓扑')}</div>
          <Input
            class='host-topo-tree__search'
            v-model={ctx.searchValue.value}
            clearable
            placeholder={t('搜索 IP / 主机名 / 节点名称')}
            type='search'
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
          <Tree
            ref={instance => {
              ctx.treeRef.value = (instance ?? null) as typeof ctx.treeRef.value;
            }}
            children='children'
            data={ctx.displayTreeData.value}
            empty-text={t('暂无数据')}
            label='name'
            level-line='1px solid #EBEEF5'
            node-content-action={nodeContentAction}
            nodeKey='id'
            prefix-icon={getPrefixIcon}
            search={{
              value: ctx.searchValue.value,
              showChildNodes: true,
            }}
            selected={ctx.selectedIds.value}
            show-node-type-icon={false}
            virtual-render
            onNodeClick={handleNodeClick}
            v-slots={{
              node: (node: ITreeSlotNode) => renderTreeNode(node),
            }}
          />
        </Loading>
      </div>
    );
  },
});
