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

import { formatTipsContent } from '../../../../../metric-chart-view/utils';

import './select-panel.scss';

interface IEmit {
  onChange: (value: IProps['value']) => void;
}
interface IProps {
  splitable: boolean;
  value: { field: string; split: boolean }[];
  data: {
    alias: string;
    name: string;
  }[];
}

@Component
export default class AppendValue extends tsc<IProps, IEmit> {
  @Prop({ type: Array, required: true }) readonly value: IProps['value'];
  @Prop({ type: Array, required: true }) readonly data: IProps['data'];
  @Prop({ type: Boolean, default: false }) readonly splitable: IProps['splitable'];

  @Ref('popoverRef') popoverRef: any;

  checkedMap: Readonly<Record<string, boolean>> = {};
  renderData: Readonly<IProps['data']> = [];
  hasSelectedAll = false;
  isPanelShow = false;

  get isSelectDisabled() {
    return this.data.length < 1;
  }

  handleFilterChange: (filterKey: string) => void;

  @Watch('data', { immediate: true })
  dataChange() {
    this.renderData = Object.freeze(this.data);
  }

  handleShowPopover() {
    if (this.isSelectDisabled) {
      return;
    }
    this.popoverRef.showHandler();
    this.renderData = Object.freeze(this.data);
    this.checkedMap = Object.freeze(
      this.value.reduce((result, item) => Object.assign(result, { [item.field]: item.split }), {})
    );
    this.hasSelectedAll = _.every(this.renderData, item => _.has(this.checkedMap, item.name));
  }

  handlePopoverShow() {
    this.isPanelShow = true;
  }

  handlePopoverhide() {
    this.isPanelShow = false;
    const result = Object.entries(this.checkedMap).map(([field, split]) => ({
      field,
      split,
    }));
    if (!_.isEqual(result, this.value)) {
      this.$emit('change', result);
    }
  }

  handleToggleAll(checkAll: boolean) {
    const latestCheckedMap = { ...this.checkedMap };
    if (checkAll) {
      this.renderData.forEach(item => {
        latestCheckedMap[item.name] = false;
      });
    } else {
      this.renderData.forEach(item => {
        delete latestCheckedMap[item.name];
      });
    }
    this.checkedMap = Object.freeze(latestCheckedMap);
  }

  handleToggleCheck(dimensionName: string) {
    const latestCheckedMap = { ...this.checkedMap };
    if (_.has(latestCheckedMap, dimensionName)) {
      delete latestCheckedMap[dimensionName];
    } else {
      latestCheckedMap[dimensionName] = false;
    }
    this.checkedMap = Object.freeze(latestCheckedMap);
  }

  handleToggleSplit(dimensionName: string) {
    const latestCheckedMap = { ...this.checkedMap };
    if (_.has(latestCheckedMap, dimensionName)) {
      latestCheckedMap[dimensionName] = !latestCheckedMap[dimensionName];
    } else {
      latestCheckedMap[dimensionName] = true;
    }
    this.checkedMap = Object.freeze(latestCheckedMap);
  }

  created() {
    this.handleFilterChange = _.throttle((filterKey: string) => {
      if (!filterKey) {
        this.renderData = Object.freeze(this.data);
      } else {
        this.renderData = Object.freeze(
          _.filter(this.data, item => {
            const keyWord = filterKey.toLocaleLowerCase();
            return item.name.toLocaleLowerCase().includes(keyWord) || item.alias.toLocaleLowerCase().includes(keyWord);
          })
        );
      }

      this.hasSelectedAll = _.every(this.renderData, item => _.has(this.checkedMap, item.name));
    }, 300);
  }

  render() {
    const renderDimensionItem = (dimensionData: IProps['data'][number]) => {
      const isChecked = _.has(this.checkedMap, dimensionData.name);
      const isSplit = this.checkedMap[dimensionData.name];
      return (
        <div
          key={dimensionData.name}
          class='item'
        >
          <bk-checkbox
            v-bk-tooltips={{ content: formatTipsContent(dimensionData.name, dimensionData.alias), placement: 'left' }}
            checked={isChecked}
            onChange={() => this.handleToggleCheck(dimensionData.name)}
          >
            {dimensionData.alias || dimensionData.name}
            {/* {dimensionData.alias && <span class='dimension-name'>{dimensionData.name}</span>} */}
          </bk-checkbox>
          {this.splitable && isChecked && (
            <bk-popover style='margin-left: auto'>
              <bk-switcher
                size='small'
                theme='primary'
                value={isSplit}
                onChange={() => this.handleToggleSplit(dimensionData.name)}
              />
              <span
                style={{
                  'margin-left': '4px',
                  color: isSplit ? '#4D4F56' : '#C4C6CC',
                }}
              >
                {this.$t('维度拆解')}
              </span>
              <div slot='content'>
                <div>{this.$t('维度拆解：')}</div>
                <div>{this.$t('关闭时，默认是根据聚合维度，画出多条线；')}</div>
                <div>{this.$t('开启后，根据聚合维度，生成多张图。')}</div>
              </div>
            </bk-popover>
          )}
        </div>
      );
    };

    return (
      <bk-popover
        ref='popoverRef'
        tippyOptions={{
          placement: 'bottom-start',
          distance: 10,
          arrow: false,
          hideOnClick: true,
          zIndex: 1002,
          onShow: this.handlePopoverShow,
          onHidden: this.handlePopoverhide,
        }}
        theme='light group-by-select-panel'
        trigger='manual'
      >
        <div
          class={{
            'group-by-select-panel': true,
            'is-disabled': this.isSelectDisabled,
          }}
          v-bk-tooltips={{
            content: this.$t('没有可聚合维度'),
            disabled: !this.isSelectDisabled,
          }}
          onClick={this.handleShowPopover}
        >
          <i class='icon-monitor icon-a-1jiahao' />
        </div>
        <div
          class='wrapper'
          slot='content'
        >
          {this.isPanelShow && (
            <div>
              <div style='padding: 0 8px'>
                <bk-input
                  behavior='simplicity'
                  clearable={true}
                  onChange={this.handleFilterChange}
                />
              </div>
              {this.renderData.length > 0 && (
                <div class='dimension-list'>
                  <div class='item'>
                    <bk-checkbox
                      false-value={false}
                      true-value={true}
                      value={this.hasSelectedAll}
                      onChange={this.handleToggleAll}
                    >
                      {this.$t('全部')}
                    </bk-checkbox>
                  </div>
                  {this.renderData.map(renderDimensionItem)}
                </div>
              )}
              {this.renderData.length < 1 && (
                <div style='color: #63656e; line-height: 32px; text-align: center;'>{this.$t('无匹配数据')}</div>
              )}
            </div>
          )}
        </div>
      </bk-popover>
    );
  }
}
