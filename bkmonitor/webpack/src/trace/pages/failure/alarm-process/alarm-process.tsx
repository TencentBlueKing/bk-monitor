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
import { defineComponent, reactive, ref } from 'vue';
import { Input, Popover, Tree } from 'bkui-vue';
import { CogShape } from 'bkui-vue/lib/icon';

import './alarm-process.scss';

export default defineComponent({
  props: {
    steps: {
      type: Array,
      default: () => []
    }
  },
  setup(props) {
    const renderStep = () => {};

    const handleSetting = () => {};

    const treeData = [
      {
        name: '系统事件',
        id: 1,
        children: [
          {
            name: '系统时间1',
            id: '1-1',
            type: 'ss'
          },
          {
            name: '系统时间1',
            id: '1-3',
            type: 'ss',
            isAddLine: true
          },
          {
            name: '系统时间1',
            id: '1-2',
            type: 's1'
          },
          {
            name: '系统时间1',
            id: '1-3',
            type: 's1'
          }
        ]
      },
      {
        name: '系统事件2',
        id: 2,
        children: [
          {
            name: '系统时间1',
            id: '2-1',
            type: 'ss'
          },
          {
            name: '系统时间1',
            id: '2-3',
            type: 'ss',
            isAddLine: true
          },
          {
            name: '系统时间1',
            id: '2-2',
            type: 's1'
          },
          {
            name: '系统时间1',
            id: '2-3',
            type: 's1'
          }
        ]
      }
    ];
    return {
      treeData,
      renderStep,
      handleSetting
    };
  },
  render() {
    return (
      <div class='alarm-process'>
        <div class='alarm-process-search'>
          <Input placeholder={this.$t('搜索 流转记录')}></Input>

          <Popover
            trigger='click'
            theme='light'
            width='242'
            extCls='alarm-process-search-setting-popover'
            placement='bottom-center'
            arrow={false}
          >
            {{
              default: (
                <span
                  v-bk-tooltips={{ content: this.$t('设置展示类型') }}
                  class='alarm-process-search-setting'
                  onClick={this.handleSetting}
                >
                  <CogShape></CogShape>
                </span>
              ),
              content: (
                <div class='alarm-process-search-setting-tree'>
                  <Tree
                    data={this.treeData}
                    node-key='id'
                    expand-all={true}
                    indent={24}
                    showNodeTypeIcon={false}
                    show-checkbox={true}
                    selectable={false}
                    prefix-icon={true}
                    label='name'
                  >
                    {{
                      default: ({ data, attributes }) => {
                        return (
                          <span class='alarm-process-search-setting-tree-node'>
                            {attributes.parent && <i class='icon-monitor icon-duihao'></i>}
                            {data.name}
                            {data.isAddLine ? <span class='node-line'></span> : ''}
                          </span>
                        );
                      }
                    }}
                  </Tree>
                </div>
              )
            }}
          </Popover>
        </div>
        <ul class='alarm-process-list'>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((_, index) => {
            return (
              <li class='alarm-process-item'>
                <div class='alarm-process-item-avatar'>
                  {index !== 8 && <span class='alarm-process-list-line'></span>}
                  <img
                    src=''
                    alt=''
                  />
                </div>
                <div class='alarm-process-item-content'>
                  <p>
                    <span class='alarm-process-item-time'>2023-10-10 00:00:00</span>
                    <span class='alarm-process-item-title'>修改故障属性</span>
                  </p>
                  <p>mimili 设置故障原因为：我是占位文案</p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }
});
