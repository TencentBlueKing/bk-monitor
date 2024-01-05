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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from '../../../../../../monitor-common/utils/utils';
import { defaultAddTimeRange } from '../meal-content/meal-content-data';

import './custom-tab.scss';

export interface IPanels {
  key?: string | number;
  name?: string;
  label?: string;
  timeValue?: string[];
}

interface ICustomTabProps {
  panels?: IPanels[];
  active?: string | number;
  type?: 'period' | 'text';
  newKey?: string;
  timeStyleType?: number;
  minIsMinute?: boolean; // 最小单位是否为分钟
}

interface ICustomTabEvent {
  onChange?: string;
  onAdd?: IPanels[];
  onDel?: string;
  onTimeChange?: { value: string[]; key: string };
}

@Component({
  name: 'CustomTab'
})
export default class CustomTab extends tsc<ICustomTabProps, ICustomTabEvent> {
  @Prop({ type: Array, default: () => [] }) panels: IPanels[];
  @Prop({ type: [String, Number], default: '' }) active: string;
  @Prop({ type: String, default: 'text' }) type: ICustomTabProps['type'];
  @Prop({ type: String, default: '' }) newKey: string;
  @Prop({ type: Number, default: 0 }) timeStyleType: number;
  @Prop({ type: Boolean, default: false }) minIsMinute: boolean;
  @Ref('customTabRef') customTabRef: HTMLDivElement;

  curActive = '';
  curPanels: IPanels[] = [];
  newItemActive = false;

  get isCanAdd() {
    return this.type === 'period'
      ? !!defaultAddTimeRange(
          this.panels.map(item => item.timeValue),
          this.minIsMinute
        ).length
      : false;
  }

  @Watch('panels', { immediate: true, deep: true })
  handlePanels(v: IPanels[]) {
    this.curPanels = deepClone(v);
  }
  @Watch('active', { immediate: true, deep: true })
  handleActive(v: string) {
    this.curActive = v;
  }

  /**
   * @description: 新增item时需高亮
   * @param {*}
   * @return {*}
   */
  @Watch('newKey')
  async handleNewKey(v: string) {
    if (v) {
      await this.$nextTick();
      this.newItemActive = true;
      const instance = window.setTimeout(() => {
        this.newItemActive = false;
        window.clearTimeout(instance);
      }, 1000);
    }
  }

  @Emit('change')
  handleChange(v: string) {
    return v;
  }
  @Emit('add')
  handleAdd() {
    return this.curPanels;
  }
  @Emit('del')
  handleDel(key: string) {
    return key;
  }

  @Emit('timeChange')
  handleTimeChange(timeArr: string[], panel: IPanels) {
    const curPanel = this.curPanels.find(item => panel.key === item.key);
    curPanel.timeValue = timeArr;
    return { value: timeArr, key: this.curActive };
  }

  handleAddPanel() {
    if (this.isCanAdd) {
      this.handleAdd();
    }
  }
  // 删除
  handleDelItem(key: string) {
    if (this.curPanels.length === 1) return;
    this.$bkInfo({
      type: 'warning',
      title: window.i18n.t('确认删除该生效时段？'),
      subTitle: window.i18n.t('删除该生效时段将会删除其包含的所有信息'),
      confirmFn: () => {
        if (this.active === key) {
          const index = this.curPanels.findIndex(item => item.key === key);
          if (index === 0) {
            this.handleChange(this.curPanels[index + 1].key as string);
          } else {
            this.handleChange(this.curPanels[index - 1].key as string);
          }
        }
        this.handleDel(key);
      }
    });
  }
  // time弹出
  handleOpenChange(state, panel: IPanels) {
    if (!state) {
      const curPanel = this.curPanels.find(item => panel.key === item.key);
      this.handleTimeChange(curPanel.timeValue, panel);
    }
  }

  // 动态tab
  renderLabel(key, item) {
    const timeClass = ['time-wrap', 'time-wrap-01'];
    return (
      <div
        class={[
          timeClass[this.timeStyleType],
          this.curActive === key ? 'active' : 'noactive',
          { 'border-active': item.key === this.newKey && this.newItemActive }
        ]}
      >
        {this.curPanels.length > 1 ? (
          <span
            class='icon-monitor icon-mc-delete-line del-btn'
            onClick={(e: Event) => {
              e.stopPropagation();
              this.handleDelItem(key);
            }}
          ></span>
        ) : undefined}
        <div class='time-title'>{this.$tc('生效时段')}</div>
        <bk-time-picker
          style={{ 'pointer-events': this.curActive !== key ? 'none' : 'auto' }}
          v-model={item.timeValue}
          format={this.minIsMinute ? 'HH:mm' : 'HH:mm:ss'}
          behavior='simplicity'
          class='time-input'
          type='timerange'
          ref={`timeinputRef${key}`}
          clearable={false}
          transfer={true}
          allowCrossDay={true}
          on-open-change={state => this.handleOpenChange(state, item)}
        ></bk-time-picker>
      </div>
    );
  }
  getTabs() {
    if (this.type === 'period') {
      const timeHeight = [64, 42];
      const timeClass = ['period-wrap', 'period-wrap-01'];
      return (
        <div class={timeClass[this.timeStyleType]}>
          <bk-tab
            ref='time-tab'
            active={this.curActive}
            labelHeight={timeHeight[this.timeStyleType]}
            addable={true}
            on-add-panel={() => this.handleAddPanel()}
            on-tab-change={this.handleChange}
          >
            {this.timeStyleType === 1 ? (
              <div
                slot='add'
                class={['custom-add', { disabled: !this.isCanAdd }]}
                onClick={() => this.handleAddPanel()}
              >
                <div class='jia'>+</div>
                <span
                  v-bk-tooltips={{
                    content: this.$t('已配置全天24小时生效时段，无需额外添加生效时段'),
                    disabled: this.isCanAdd
                  }}
                >
                  {this.$t('生效时段')}
                </span>
              </div>
            ) : undefined}
            {this.curPanels.map(item => (
              <bk-tab-panel
                key={item.key}
                name={item.key}
                renderLabel={(h, name) => this.renderLabel(name, item)}
              ></bk-tab-panel>
            ))}
          </bk-tab>
        </div>
      );
    }
    if (this.type === 'text') {
      return (
        <bk-tab
          active={this.curActive}
          on-tab-change={this.handleChange}
        >
          {this.curPanels.map(item => (
            <bk-tab-panel
              key={item.key}
              name={item.key}
              label={item.label}
            ></bk-tab-panel>
          ))}
        </bk-tab>
      );
    }
  }

  render() {
    return (
      <div
        class='custom-tab-component'
        ref='customTabRef'
      >
        {this.getTabs()}
      </div>
    );
  }
}
