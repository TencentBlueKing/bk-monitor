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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SetMealAddModule from '../../../../../../store/modules/set-meal-add';

import './variable-list.scss';

const { i18n } = window;

interface IVariableListProps {
  pluginType?: string;
}
@Component({
  name: 'VariableList'
})
export default class VariableList extends tsc<IVariableListProps> {
  @Prop({ default: '', type: String }) pluginType: string;
  tablePopover = null;
  variableActive = 'alert';

  get variablePanels() {
    return SetMealAddModule.getVariablePanels.filter(item =>
      // 只有通知套餐有内容变量
      this.pluginType === 'notice' ? true : item.name !== 'CONTENT_VAR'
    );
  }
  get variableTable() {
    return SetMealAddModule.getVariableTable;
  }

  handleTap(name) {
    this.variableActive = name;
  }
  // tip
  getContent(name) {
    return `<div>
      <div>${this.$tc('变量示例')}：${name}</div>
      <div>[${this.$tc('点击复制变量')}]</div>
    </div>`;
  }
  // 移入表格行内时
  handleRowEnter(index, row, event) {
    this.handleRowLeave();
    this.tablePopover =
      this.tablePopover ||
      this.$bkPopover(row.target, {
        content: this.getContent(event.example),
        arrow: true,
        boundary: 'window',
        placement: 'top-end',
        offset: '-50, 0',
        extCls: 'meal-variable-tip'
      });
    if (this.tablePopover) {
      this.tablePopover.show(100);
    }
  }
  // 移出表格行内时
  handleRowLeave() {
    if (this.tablePopover) {
      this.tablePopover.destroy();
      this.tablePopover = null;
    }
  }

  handleRowClick(row) {
    this.copyValue(row.name);
  }

  // 复制到粘贴板
  copyValue(name) {
    const input = document.createElement('input');
    document.body.appendChild(input);
    input.setAttribute('value', `{{${name}}}`);
    input.select();
    if (document.execCommand('copy')) {
      document.execCommand('copy');
      this.$bkMessage({
        theme: 'success',
        message: `${i18n.t('已复制到剪贴板')}。`
      });
    }
    document.body.removeChild(input);
  }

  protected render() {
    const scopedSlots = {
      default: props => <span>{props.row.name}</span>
    };
    return (
      <div class='variable-content'>
        {this.variablePanels?.length ? (
          <bk-tab
            on-tab-change={this.handleTap}
            {...{
              props: {
                active: this.variableActive,
                type: 'unborder-card'
              }
            }}
          >
            {this.variablePanels.map((item, index) => (
              <bk-tab-panel
                {...{ props: item }}
                key={index}
              ></bk-tab-panel>
            ))}
          </bk-tab>
        ) : undefined}
        <div class='variable-table'>
          <bk-table
            {...{
              props: {
                data: this.variableTable[this.variableActive]
              }
            }}
            on-row-mouse-enter={this.handleRowEnter}
            on-row-mouse-leave={this.handleRowLeave}
            on-row-click={this.handleRowClick}
          >
            <bk-table-column
              label={this.$t('变量名')}
              {...{ scopedSlots }}
            ></bk-table-column>
            <bk-table-column
              {...{
                props: {
                  label: this.$t('含义'),
                  prop: 'desc'
                }
              }}
            ></bk-table-column>
          </bk-table>
        </div>
      </div>
    );
  }
}
