/*
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
 */

import { defineComponent, ref } from 'vue';

import { t } from '@/hooks/use-locale';

import type { LogItem } from '../types';

import './index.scss';

export default defineComponent({
  name: 'LogDetailPanel',
  props: {
    /** 左侧任务列表是否收起 */
    isTaskListCollapsed: {
      type: Boolean,
      default: false,
    },
    /** 当前选中的日志条目 */
    selectedLogItem: {
      type: Object as () => LogItem | null,
      default: null,
    },
  },
  emits: ['expand'],
  setup(props, { emit }) {
    /** 当前激活的标签页 */
    const activeTab = ref('original-log');

    /** 所有文件夹节点 ID（用于默认全部展开） */
    const allFolderIds: Iterable<any> | null | undefined = [];

    /** 当前选中的文件节点 ID - 默认选中第一个文件 */
    const selectedFileId = ref<string | null>('');

    /** 展开的文件夹节点 ID 集合 - 默认全部展开 */
    const expandedNodeIds = ref<Set<string>>(new Set(allFolderIds));

    /** 文件树数据 */
    const fileTreeData = ref([]);

    /** 标签页列表 */
    const panels = ref([
      {
        name: 'original-log',
        label: t('原始日志'),
        icon: 'bklog-icon bklog-log',
      },
    ]);

    /** 点击展开图标 */
    const handleExpand = () => {
      emit('expand');
    };

    /** 文件树节点点击 */
    const handleNodeClick = (node: any) => {
      if (!node.children || !node.children.length) {
        selectedFileId.value = node.id;
      }
    };

    /** 文件树展开/收起变化 */
    const handleExpandChange = (node: any) => {
      if (node.expanded) {
        expandedNodeIds.value.add(node.id);
      } else {
        expandedNodeIds.value.delete(node.id);
      }
      expandedNodeIds.value = new Set(expandedNodeIds.value);
    };

    /** 渲染文件树节点图标 */
    const renderTreeNodeIcon = (data: any) => {
      const isFolder = data.children && data.children.length;
      if (isFolder) {
        const isExpanded = expandedNodeIds.value.has(data.id);
        return (
          <i
            class={`bklog-icon ${isExpanded ? 'bklog-file-open' : 'bklog-file-close'}`}
          />
        );
      }
      return <i class='bklog-icon bklog-document' />;
    };

    /** 渲染原始日志面板内容 */
    const renderOriginalLogContent = () => (
      <div class='original-log-content'>
        {/* 左侧文件树 */}
        <div class='file-tree-sidebar'>
          <bk-big-tree
            data={fileTreeData.value}
            default-expanded-nodes={allFolderIds}
            expand-on-click={true}
            on-node-click={handleNodeClick}
            on-expand-change={handleExpandChange}
            options={{ nameKey: 'name', idKey: 'id', childrenKey: 'children' }}
            scopedSlots={{
              default: ({ data }: any) => (
                <div class='tree-node-content'>
                  {renderTreeNodeIcon(data)}
                  <span class='node-name'>{data.name}</span>
                </div>
              ),
            }}
          />
        </div>
        {/* 右侧文件内容展示：上部工具栏 + 下部日志内容 */}
        <div class='file-content-area'>
          {/* 工具栏 */}
          <div class='toolbar-wrapper' key='toolbar'></div>,{/* 日志内容区 */}
          <div class='log-content-scroll' key='log-content'></div>,
        </div>
      </div>
    );

    return () => (
      <div class='card-base log-detail-panel'>
        {/* 左上角展开图标 - 仅在左侧列表收起时显示 */}
        {props.isTaskListCollapsed && (
          <span class='expand-icon' onClick={handleExpand}>
            <i class='bklog-icon bklog-collapse'></i>
          </span>
        )}

        {/* 日志详情内容区域 */}
        <div class='log-detail-content'>
          {/* 头部 */}
          <header class='detail-header'>
            <div class='header-left'>
              <h2 class='title'>{t('日志详情')}</h2>
              {props.selectedLogItem?.model && (
                <span class='device-info'>
                  {props.selectedLogItem.model}
                </span>
              )}
              {props.selectedLogItem?.os_version && (
                <span class='device-info'>{props.selectedLogItem.os_version}</span>
              )}
              {props.selectedLogItem?.sdk_version && (
                <span class='device-info'>
                  {props.selectedLogItem.sdk_version}
                </span>
              )}
            </div>
            <div class='header-right'>
              <bk-button>
                <i class='bk-icon icon-download'></i>
                {t('下载')}
              </bk-button>
              <bk-button>
                <i class='bklog-icon bklog-share-fenxiang'></i>
                {t('分享')}
              </bk-button>
            </div>
          </header>

          {/* 标签页 */}
          <div class='tab-container'>
            <bk-tab
              active={activeTab.value}
              type='unborder-card'
              label-height={40}
              on-tab-change={(val: string) => {
                activeTab.value = val;
              }}
            >
              {panels.value.map(panel => (
                <bk-tab-panel
                  key={panel.name}
                  name={panel.name}
                  label={panel.label}
                  renderLabel={() => (
                    <div>
                      <i class={`bklog-icon ${panel.icon}`}></i>
                      <span class='panel-name'>{panel.label}</span>
                    </div>
                  )}
                >
                  {activeTab.value === 'original-log'
                    && renderOriginalLogContent()}
                </bk-tab-panel>
              ))}
            </bk-tab>
          </div>
        </div>
      </div>
    );
  },
});
