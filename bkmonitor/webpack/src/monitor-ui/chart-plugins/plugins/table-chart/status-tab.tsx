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
import { Component, Emit, Model, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { ITableFilterItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './status-tab.scss';

interface IEvents {
  onChange: string;
}
interface IProps {
  disabledClickZero?: boolean;
  needAll?: boolean;
  needExpand?: boolean;
  statusList: ITableFilterItem[];
  value?: string;
}
@Component
export default class StatusTab extends tsc<IProps, IEvents> {
  /** 是否需要全部选项 */
  @Prop({ type: Boolean, default: true }) needAll: boolean;
  /** 数据为零时候点击事件不生效 */
  @Prop({ type: Boolean, default: false }) disabledClickZero: boolean;
  @Prop({ type: Array, default: () => [] }) statusList: ITableFilterItem[];
  /* 是否可收缩 */
  @Prop({ type: Boolean, default: false }) needExpand: boolean;
  @Model('change', { type: String, default: 'all' }) value: string;

  defaultList: ITableFilterItem[] = [
    {
      id: 'all',
      name: window.i18n.t('全部'),
    },
  ];

  isExpand = false;

  @Emit('change')
  valueChange(val: string) {
    return val;
  }

  /** 点击选中 */
  handleClickItem(item: ITableFilterItem) {
    if (item.name === 0 && this.disabledClickZero) {
      return;
    }
    this.valueChange(item.id);
  }

  get localStatusList(): ITableFilterItem[] {
    const list = [...(this.needAll ? this.defaultList : []), ...this.statusList];
    if (this.needExpand) {
      return this.isExpand ? list : list.slice(0, 1);
    }
    return list;
  }

  render() {
    return (
      <div class='status-tab-wrap'>
        {this.localStatusList.map(item => (
          <span
            key={item.id}
            class={['common-status-wrap status-tab-item', { active: this.value === item.id }]}
            v-bk-tooltips={{
              content: item.tips,
              placements: ['top'],
              boundary: 'window',
              disabled: !item.tips,
              delay: 200,
              allowHTML: false,
            }}
            onClick={() => this.handleClickItem(item)}
          >
            {item.status && <span class={['common-status-icon', `status-${item.status}`]} />}
            {item.icon && <i class={['icon-monitor', item.icon]} />}
            {(!!item.name || item.name === 0) && <span class='status-count'>{item.name}</span>}
          </span>
        ))}
        {this.needExpand && (
          <div
            class={['expand-btn', { expand: this.isExpand }]}
            onClick={() => {
              this.isExpand = !this.isExpand;
            }}
          >
            <span class='icon-monitor icon-arrow-right' />
          </div>
        )}
      </div>
    );
  }
}
