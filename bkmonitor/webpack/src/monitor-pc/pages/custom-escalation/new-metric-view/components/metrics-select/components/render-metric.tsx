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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './render-metric.scss';

interface IProps {
  data: {
    alias: string;
    metric_name: string;
  };
}

@Component
export default class RenderMetric extends tsc<IProps> {
  @Prop({ type: Object, required: true }) readonly data: IProps['data'];

  @Ref('popoverRef') popoverRef: any;
  @Ref('inputRef') inputRef: any;

  isActive = false;
  isSubmiting = false;

  handleEditShow() {
    this.isActive = true;
    setTimeout(() => {
      this.inputRef.focus();
    });
  }

  handleEditHidden() {
    this.isActive = false;
  }

  handleSubmit() {
    this.isSubmiting = true;
    this.popoverRef.hideHandler();
  }

  handleCancel() {
    this.popoverRef.hideHandler();
  }

  render() {
    return (
      <div
        key={this.data.metric_name}
        class={{
          'render-metric-group-item': true,
          'is-active': this.isActive,
        }}
      >
        <bk-checkbox value={this.data.metric_name}>{this.data.metric_name}</bk-checkbox>
        <bk-popover
          ref='popoverRef'
          tippyOptions={{
            placement: 'bottom-start',
            distance: 8,
            theme: 'light edit-metric-alias-name',
            trigger: 'click',
            hideOnClick: true,
            onShow: this.handleEditShow,
            onHidden: this.handleEditHidden,
          }}
        >
          <div class='metric-edit-btn'>
            <i class='icon-monitor icon-bianji' />
          </div>
          <div slot='content'>
            <div class='wrapper'>
              <div class='title'>{this.$t('编辑指标别名')}</div>
              <div>
                <span style='color: #63656E;'>{this.$t('指标名：')}</span>
                <span>{this.data.metric_name}</span>
              </div>
              <div style='margin: 8px 0 6px; color: #4D4F56;'>{this.$t('指标别名：')}</div>
              <bk-input
                ref='inputRef'
                value={this.data.alias}
              />
            </div>
            <div class='footer'>
              <bk-button theme='primary'>{this.$t('确定')}</bk-button>
              <bk-button
                style='margin-left: 8px'
                onClick={this.handleCancel}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
        </bk-popover>
      </div>
    );
  }
}
