/*
 * @Date: 2021-06-14 15:39:58
 * @LastEditTime: 2021-06-15 16:45:02
 * @Description:
 */
import type { VNode } from 'vue';

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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { TranslateResult } from 'vue-i18n';

import './group.scss';

export interface IGroupData {
  data: any[]; // data为自定义分组数据
  id: number | string;
  name: TranslateResult;
}
interface IGroupEvents {
  onClear: (item: IGroupData) => void;
}
interface IGroupProps {
  customTitleSlot?: titleSlotType; // 自定义title
  data?: IGroupData[]; // 数据源
  defaultActiveName?: string[]; // 默认展开项
  theme?: themeType; // 主题
}

interface IGroupSlots {
  default: { item: IGroupData };
}

type TActiveName = (number | string)[];

type themeType = 'bold' | 'filter';

type titleSlotType = (item: IGroupData) => VNode;

/**
 * 插件分组信息
 */
@Component({
  name: 'Group',
})
export default class Group extends tsc<IGroupProps, IGroupEvents, IGroupSlots> {
  @Prop({ type: Array, default: () => [] }) readonly data: IGroupData[];
  @Prop({ type: String, default: '' }) readonly theme: themeType;
  @Prop({ type: Array, default: () => [] }) readonly defaultActiveName!: TActiveName;
  @Prop({ type: Function, default: undefined }) readonly customTitleSlot: titleSlotType;

  activeName: TActiveName = [];

  created() {
    this.activeName = this.defaultActiveName;
  }

  /**
   * 自定义title（内置两种样式）
   * @param item
   * @returns
   */
  titleSlot(item: IGroupData): VNode {
    if (this.customTitleSlot) return this.customTitleSlot(item);

    return this.theme === 'bold' ? this.boldTitleSlot(item) : this.filterTitleTheme(item);
  }

  /**
   * 插件分组样式
   * @param item
   * @returns
   */
  boldTitleSlot(item: IGroupData): VNode {
    return (
      <div class='group-title bold'>
        <i class={['bk-icon icon-angle-right', { expand: this.activeName?.includes(item.id) }]} />
        <span class='name'>{item.name}</span>
      </div>
    );
  }

  /**
   * 筛选分组样式
   * @param item
   * @returns
   */
  filterTitleTheme(item: IGroupData): VNode {
    return (
      <div class='group-title filter'>
        <div class='title-left'>
          <i class={['icon-monitor icon-mc-arrow-down', { expand: this.activeName.includes(item.id) }]} />
          <span class='name'>{item.name}</span>
        </div>
        <i
          class='icon-monitor icon-a-Clearqingkong'
          v-bk-tooltips={{ content: this.$t('清除已勾选') }}
          onClick={event => this.handleClearChecked(event, item)}
        />
      </div>
    );
  }

  @Emit('clear')
  handleClearChecked(event: Event, item: IGroupData) {
    event.stopPropagation();
    return item;
  }

  render() {
    return (
      <bk-collapse vModel={this.activeName}>
        {this.data?.map(item =>
          item.data.length > 0 ? (
            <bk-collapse-item
              key={item.id}
              ext-cls={`collapse-item collapse-item-${this.theme}`}
              scopedSlots={{
                default: () => this.titleSlot(item),
                content: () => this.$scopedSlots?.default?.({ item }),
              }}
              name={item.id}
              hide-arrow
            />
          ) : undefined
        )}
      </bk-collapse>
    );
  }
}
