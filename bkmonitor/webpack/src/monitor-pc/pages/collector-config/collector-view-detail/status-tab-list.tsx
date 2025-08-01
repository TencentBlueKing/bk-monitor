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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './status-tab-list.scss';

export interface IStatusData {
  [propsName: string]: { count?: number };
}
interface IStatusTablListEvents {
  onChange?: string;
}

interface IStatusTablListProps {
  statusData?: IStatusData;
  type?: string;
}

interface ITab {
  color?: string;
  name?: string;
  tips?: string;
  type: string;
}

@Component({
  name: 'StatusTablList',
})
export default class StatusTablList extends tsc<IStatusTablListProps, IStatusTablListEvents> {
  @Prop({ type: String, default: 'all' }) type: string;
  @Prop({
    type: Object,
    default: () => ({
      success: { count: 0 },
      failed: { count: 0 },
      nodata: { count: 0 },
    }),
  })
  statusData: IStatusData;

  tabList: ITab[] = [
    {
      name: window.i18n.tc('全部'),
      type: 'all',
    },
    {
      type: 'success',
      tips: `${window.i18n.t('正常')}  (${window.i18n.t('近3个周期数据')})`,
      color: 'success',
    },
    {
      type: 'failed',
      tips: `${window.i18n.t('异常')}  (${window.i18n.t('下发采集失败')})`,
      color: 'failed',
    },
    {
      type: 'nodata',
      tips: `${window.i18n.t('无数据')}  (${window.i18n.t('近3个周期数据')})`,
      color: 'nodata',
    },
  ];

  handleClickTab(item: ITab) {
    if (item.type !== 'all' && !this.statusData?.[item.type]?.count) return;
    this.handleChange(item.type);
  }

  @Emit('change')
  handleChange(v: string) {
    return v;
  }

  render() {
    return (
      <div class='collect-view-status-tab'>
        {this.tabList.map(item => (
          <div
            key={item.type}
            class={['tab-item', { active: item.type === this.type }]}
            v-bk-tooltips={{ content: item?.tips || '', disabled: item.type === 'all', allowHTML: false }}
            onClick={() => this.handleClickTab(item)}
          >
            {item.type !== 'all' ? <span class={['dots', item.color]} /> : undefined}
            <span>{item.type === 'all' ? item.name : this.statusData?.[item.type]?.count || 0}</span>
          </div>
        ))}
      </div>
    );
  }
}
