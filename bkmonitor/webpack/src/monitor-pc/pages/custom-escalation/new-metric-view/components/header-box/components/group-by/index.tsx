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

import { formatTipsContent } from '../../../../metric-chart-view/utils';
import SelectPanel from './components/select-panel';
import customEscalationViewStore from '@store/modules/custom-escalation-view';

import './index.scss';

interface IEmit {
  onChange: (value: IProps['value']) => void;
}

interface IProps {
  splitable?: boolean;
  customDemensionList?: {
    alias: string;
    name: string;
  }[];
  value: {
    field: string;
    split: boolean;
  }[];
}

@Component
export default class AggregateDimensions extends tsc<IProps, IEmit> {
  @Prop({ type: Array, required: true }) readonly value: IProps['value'];
  @Prop({ type: Boolean, default: false }) readonly splitable: IProps['splitable'];
  @Prop({ type: Array }) readonly customDemensionList: IProps['customDemensionList'];

  @Ref('rootRef') rootRef: HTMLElement;
  @Ref('wrapperRef') wrapperRef: HTMLElement;
  @Ref('calcTagListRef') calcTagListRef: HTMLElement;

  isCalcRenderTagNum = true;
  localValueList: Readonly<IProps['value']> = [];
  isWholeLine = false;
  renderTagNum = 0;

  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }

  get dimensionAliasNameMap() {
    return customEscalationViewStore.dimensionAliasNameMap;
  }

  get demensionList() {
    if (this.customDemensionList) {
      return this.customDemensionList;
    }
    const demenesionNameMap = {};
    return this.currentSelectedMetricList.reduce<{ alias: string; name: string }[]>((result, item) => {
      for (const demesionItem of item.dimensions) {
        if (!demenesionNameMap[demesionItem.name]) {
          result.push(demesionItem);
          demenesionNameMap[demesionItem.name] = true;
        }
      }
      return result;
    }, []);
  }

  get renderValueList() {
    return this.localValueList.slice(0, this.renderTagNum);
  }

  get moreValueCount() {
    return this.localValueList.length - this.renderValueList.length;
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localValueList = Object.freeze([...this.value]);
    this.calcWholeLine();
    this.calcRenderTagNum();
  }

  calcRenderTagNum() {
    // next 确保组件是 mounted 状态
    setTimeout(() => {
      if (!this.wrapperRef || this.localValueList.length < 1 || !this.isWholeLine) {
        this.renderTagNum = this.localValueList.length;
        return;
      }

      this.isCalcRenderTagNum = true;
      // setTimeout 确保 isCalcRenderTagNum 已经生效
      this.$nextTick(() => {
        const { width: maxWidth } = this.wrapperRef.getBoundingClientRect();

        this.renderTagNum = 0;

        let renderTagCount = 0;
        const labelWidth = 80;
        const tipsTagPlaceholderWidth = 45;
        const selectBtnWidth = 60;
        const clearBtnWidth = 30;

        const allTagEleList = Array.from(this.calcTagListRef!.querySelectorAll('.value-item'));
        if (
          this.calcTagListRef!.getBoundingClientRect().width + selectBtnWidth + labelWidth + clearBtnWidth <=
            maxWidth ||
          this.localValueList.length === 1
        ) {
          this.renderTagNum = this.localValueList.length;
        } else {
          const tagMargin = 6;
          let totalTagWidth = -tagMargin;
          // eslint-disable-next-line @typescript-eslint/prefer-for-of
          for (let i = 0; i < allTagEleList.length; i++) {
            const { width: tagWidth } = allTagEleList[i].getBoundingClientRect();
            totalTagWidth += tagWidth + tagMargin;
            if (totalTagWidth + tipsTagPlaceholderWidth + selectBtnWidth + labelWidth + clearBtnWidth <= maxWidth) {
              renderTagCount = renderTagCount + 1;
            } else {
              break;
            }
          }
          this.renderTagNum = Math.max(renderTagCount, 1);
        }

        this.isCalcRenderTagNum = false;
      });
    });
  }

  calcWholeLine() {
    this.$nextTick(() => {
      if (!this.rootRef) {
        return;
      }
      const totalWrapperWidth = this.rootRef.parentElement.clientWidth;
      const itemsTotalWidth = Array.from(this.rootRef.parentElement.children).reduce((result, childEle) => {
        if (childEle === this.rootRef) {
          return (
            result +
            Array.from(this.wrapperRef.children).reduce(
              (childWidthTotal, childItem) => childWidthTotal + childItem.getBoundingClientRect().width,
              0
            )
          );
        }
        return result + childEle.clientWidth;
      }, 0);
      this.isWholeLine = totalWrapperWidth < itemsTotalWidth + 120;
    });
  }

  triggerChange() {
    this.$emit('change', this.localValueList);
    // this.renderTagNum = this.localValueList.length;
    this.calcRenderTagNum();
  }

  handleChange(value: IProps['value']) {
    this.localValueList = Object.freeze(value);
    this.triggerChange();
  }

  handleRemove(index: number) {
    const localValueList = [...this.localValueList];
    localValueList.splice(index, 1);
    this.localValueList = Object.freeze(localValueList);
    this.triggerChange();
  }

  handleClear() {
    this.localValueList = [];
    this.triggerChange();
  }

  mounted() {
    this.calcWholeLine();
    this.calcRenderTagNum();
    const resizeObserver = new ResizeObserver(
      _.throttle(() => {
        this.calcWholeLine();
        this.calcRenderTagNum();
      }, 300)
    );
    resizeObserver.observe(this.rootRef.parentElement);
    this.$once('hook:beforeDestroy', () => {
      resizeObserver.disconnect();
    });
  }

  render() {
    const renderField = (data: { field: string }) => {
      return (
        <span
          v-bk-tooltips={{
            content: formatTipsContent(data.field, this.dimensionAliasNameMap[data.field]),
            placement: 'bottom',
          }}
        >
          {this.dimensionAliasNameMap[data.field] || data.field}
        </span>
      );
      // return this.dimensionAliasNameMap[data.field]
      //   ? `${this.dimensionAliasNameMap[data.field]} (${data.field})`
      //   : data.field;
    };
    return (
      <div
        ref='rootRef'
        style={{
          width: this.isWholeLine ? '100%' : 'auto',
        }}
        class='new-metric-view-group-by'
      >
        <div
          ref='wrapperRef'
          class='wrapper'
        >
          <div
            class='label'
            data-role='param-label'
          >
            <div>{this.$t('聚合维度')}</div>
          </div>
          <div class='value-wrapper'>
            {this.renderValueList.map((item, index) => (
              <div
                key={item.field}
                class={{
                  'value-item': true,
                  'is-split': item.split,
                }}
              >
                {item.split && <i class='icon-monitor icon-chaitu split-flag' />}
                {renderField(item)}
                <i
                  class='icon-monitor icon-mc-close remote-btn'
                  onClick={() => this.handleRemove(index)}
                />
              </div>
            ))}
            {this.moreValueCount > 0 && (
              <bk-popover theme='light new-metric-view-group-by-more'>
                <div
                  key='more'
                  class='value-item'
                >
                  + {this.moreValueCount}
                </div>
                <div slot='content'>
                  {this.localValueList.slice(this.renderTagNum).map((item, index) => (
                    <div
                      key={item.field}
                      class='value-item'
                    >
                      {item.split && <i class='icon-monitor icon-chaitu split-flag' />}
                      {renderField(item)}
                      <i
                        class='icon-monitor icon-mc-close remote-btn'
                        onClick={() => this.handleRemove(index)}
                      />
                    </div>
                  ))}
                </div>
              </bk-popover>
            )}
            {this.isCalcRenderTagNum && (
              <div
                ref='calcTagListRef'
                style='position: absolute; word-break: keep-all; white-space: nowrap; visibility: hidden'
              >
                {this.localValueList.map((item, index) => (
                  <div
                    key={item.field}
                    class='value-item'
                  >
                    {item.split && <i class='icon-monitor icon-chaitu split-flag' />}
                    {item.field}
                    <i
                      class='icon-monitor icon-mc-close remote-btn'
                      onClick={() => this.handleRemove(index)}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
          <SelectPanel
            style='margin-left: 6px'
            data={this.demensionList}
            splitable={this.splitable}
            value={this.localValueList as IProps['value']}
            onChange={this.handleChange}
          />
          {this.localValueList.length > 0 && (
            <div
              class='clear-btn'
              v-bk-tooltips={this.$t('清空')}
              onClick={this.handleClear}
            >
              <i class='icon-monitor icon-a-Clearqingkong' />
            </div>
          )}
        </div>
      </div>
    );
  }
}
