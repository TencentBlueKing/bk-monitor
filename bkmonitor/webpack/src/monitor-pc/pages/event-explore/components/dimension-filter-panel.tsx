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

import { Component, Emit, Ref, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { eventTopK } from 'monitor-api/modules/data_explorer';

import type { IDimensionField, IFormData } from '../typing';

import './dimension-filter-panel.scss';

interface DimensionFilterPanelProps {
  formData: IFormData;
  list: IDimensionField[];
}

interface DimensionFilterPanelEvents {
  onClose(): void;
}

@Component
export default class DimensionFilterPanel extends tsc<DimensionFilterPanelProps, DimensionFilterPanelEvents> {
  @Prop() formData!: IFormData;
  @Prop({ default: () => [] }) list!: IDimensionField[];

  @Ref('dimensionPopover') dimensionPopoverRef!: HTMLDivElement;

  @InjectReactive('formatTimeRange') formatTimeRange;

  typeIconMap = {
    keyword: 'icon-string',
    text: 'icon-text',
    interger: 'icon-number',
    date: 'icon-mc-time',
  };

  fieldListCount = {};

  searchVal = '';

  activeField = '';
  popoverInstance = null;

  @Watch('list')
  async handleListChange() {
    const list = await this.getFieldTopK({
      limit: 0,
      fields: this.list.reduce((pre, cur) => {
        if (cur.is_option_enabled) pre.push(cur.name);
        return pre;
      }, []),
    });
    this.fieldListCount = list.reduce((pre, cur) => {
      pre[cur.field] = cur.distinct_count;
      return pre;
    }, {});
  }

  async handleDimensionItemClick(e: Event, item) {
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
    this.activeField = item.name;
    if (!item.is_option_enabled) return;
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.dimensionPopoverRef,
      placement: 'right',
      width: 400,
      distance: -5,
      boundary: 'window',
      trigger: 'manul',
      theme: 'light event-retrieval-dimension-filter',
      arrow: true,
      interactive: true,
      onHide: () => {
        this.activeField = '';
      },
    });
    const list = await this.getFieldTopK({
      limit: 5,
      fields: [item.name],
    });
    console.log(list);
    this.popoverInstance?.show(100);
  }

  getFieldTopK(params) {
    const { result_table_id, ...formData } = this.formData; //
    return eventTopK({
      query_configs: [
        {
          ...formData,
          table: this.formData.result_table_id,
        },
      ],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
      ...params,
    }).catch(() => []);
  }

  @Emit('close')
  handleClose() {}

  render() {
    return (
      <div class='dimension-filter-panel-comp'>
        <div class='header'>
          <div class='title'>{this.$t('维度过滤')}</div>
          <i
            class='icon-monitor icon-back-left'
            onClick={this.handleClose}
          />
        </div>
        <div class='search-input'>
          <bk-input
            v-model={this.searchVal}
            placeholder={this.$t('搜索 维度字段')}
            right-icon='bk-icon icon-search'
          />
        </div>

        <div class='dimension-list'>
          {this.list.map(item => (
            <div
              key={item.name}
              class={{ 'dimension-item': true, active: this.activeField === item.name }}
              onClick={e => this.handleDimensionItemClick(e, item)}
            >
              <span class={['icon-monitor', this.typeIconMap[item.type], 'type-icon']} />
              <span
                class='dimension-name'
                v-bk-overflow-tips
              >
                {item.alias}
              </span>
              {item.is_option_enabled && <span class='dimension-count'>{this.fieldListCount[item.name] || 0}</span>}
            </div>
          ))}
        </div>

        <div style={{ display: 'none' }}>
          <div
            ref='dimensionPopover'
            class='event-retrieval-dimension-filter-content'
          >
            <div class='popover-header'>
              <div class='title'>
                {this.activeField}
                {this.$t('去重后的字段统计')}
              </div>
              <div class='count'>12</div>
            </div>

            <div class='field-list'>
              <div class='field-item'>
                <div class='filter-tools'>
                  <i class='icon-monitor icon-a-sousuo' />
                  <i class='icon-monitor icon-sousuo-' />
                </div>
                <div class='progress-content'>
                  <div class='info-text'>
                    <span class='field-name'>11.154.121.234</span>
                    <span class='counts'>
                      <span class='total'>13条</span>
                      <span class='progress-count'>24%</span>
                    </span>
                  </div>
                  <bk-progress
                    color='#5AB8A8'
                    percent={0.24}
                    show-text={false}
                    stroke-width={6}
                  />
                </div>
              </div>
              <div class='load-more'>{this.$t('更多')}</div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
