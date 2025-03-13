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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';
import { makeMap } from 'monitor-common/utils/make-map';

import EditOffset from './edit-offset';

import './index.scss';

interface IProps {
  value: {
    type: string;
    offset: string[];
  };
  exclude?: Array<'metric' | 'time'>;
}

interface IEmit {
  onChange: (value: IProps['value']) => void;
}

@Component
export default class CompareType extends tsc<IProps, IEmit> {
  @Prop({ type: Object, default: () => ({ type: '', offset: [] }) }) readonly value: IProps['value'];
  @Prop({ type: Array, default: () => [] }) readonly exclude: IProps['exclude'];

  @Ref('popoverRef') popoverRef: any;

  typeList = Object.freeze([
    {
      id: '',
      name: this.$t('不对比'),
    },
    {
      id: 'time',
      name: this.$t('时间对比'),
    },
    {
      id: 'metric',
      name: this.$t('指标对比'),
    },
  ]);

  localType = '';
  localOffset: string[] = [];

  get currentTypeName() {
    return _.find(this.typeList, item => item.id === this.localType).name;
  }

  get isShowEditOffset() {
    return this.localType === 'time';
  }

  get renderTypeList() {
    const excludeMap = makeMap(this.exclude);
    return _.filter(this.typeList, item => !excludeMap[item.id]);
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localType = this.value.type;
    this.localOffset = this.value.offset;
  }

  triggerChange() {
    this.$emit('change', {
      type: this.localType,
      offset: this.localOffset,
    });
  }

  handleTypeChange(type: string) {
    this.localType = type;
    if (type !== 'time') {
      this.localOffset = [];
      this.triggerChange();
    }
    this.popoverRef.hideHandler();
  }

  handleOffsetChange(offset: string[]) {
    this.localOffset = offset;
    this.triggerChange();
  }

  render() {
    return (
      <div class='new-metric-view-compare-type'>
        <div
          class='label'
          role='param-label'
        >
          <div>{this.$t('对比')}</div>
        </div>
        <bk-popover
          ref='popoverRef'
          tippy-options={{
            placement: 'bottom',
            arrow: false,
            distance: 8,
            hideOnClick: true,
          }}
          theme='light new-metric-view-compare-type'
          trigger='click'
        >
          <div style='display: flex; align-items: center; height: 34px; padding: 0 6px; cursor: pointer'>
            {this.currentTypeName}
            <i class='icon-monitor icon-mc-triangle-down' />
          </div>
          <div
            class='wrapper'
            slot='content'
          >
            {this.renderTypeList.map(item => (
              <div
                key={item.id}
                class={{
                  'compare-type-item': true,
                  'is-active': item.id === this.localType,
                }}
                onClick={() => this.handleTypeChange(item.id)}
              >
                {item.name}
              </div>
            ))}
          </div>
        </bk-popover>
        {this.isShowEditOffset && (
          <EditOffset
            value={this.value.offset}
            onChange={this.handleOffsetChange}
          />
        )}
      </div>
    );
  }
}
