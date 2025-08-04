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

import { modifyCustomTsFields } from 'monitor-api/modules/custom_report';

import './render-metric.scss';

interface IEmit {
  onCheckChange: (checked: boolean) => void;
  onEditSuccess: () => void;
}

interface IProps {
  checked?: boolean;
  data: {
    alias: string;
    metric_name: string;
  };
}

@Component
export default class RenderMetric extends tsc<IProps, IEmit> {
  @Prop({ type: Object, required: true }) readonly data: IProps['data'];
  @Prop({ type: Boolean, default: false }) readonly checked: IProps['checked'];

  @Ref('fromRef') fromRef: any;
  @Ref('popoverRef') popoverRef: any;
  @Ref('inputRef') inputRef: any;

  isActive = false;
  isSubmiting = false;
  formData = {
    description: '',
  };

  get formRules() {
    return Object.freeze({
      description: [],
    });
  }

  @Watch('data', { immediate: true })
  dataChange() {
    this.formData.description = this.data.alias;
  }

  handleChange(checked: boolean) {
    this.$emit('checkChange', checked);
  }

  handleEditShow() {
    this.isActive = true;
    setTimeout(() => {
      this.inputRef.focus();
    });
  }

  handleEditHidden() {
    this.isActive = false;
  }

  async handleSubmit() {
    this.isSubmiting = true;
    try {
      await this.fromRef.validate();
      await modifyCustomTsFields({
        time_series_group_id: this.$route.params.id,
        update_fields: [
          {
            type: 'metric',
            name: this.data.metric_name,
            ...this.formData,
          },
        ],
      });
      this.popoverRef.hideHandler();
      this.$emit('editSuccess');
    } finally {
      this.isSubmiting = false;
    }
  }

  handleCancel() {
    this.popoverRef.hideHandler();
  }

  render() {
    return (
      <bk-popover
        style='display: block'
        class={{
          'metric-select-metric-item': true,
          'is-active': this.isActive,
        }}
        placement='right'
      >
        <div class='content-wrapper'>
          <bk-checkbox
            checked={this.checked}
            onChange={this.handleChange}
          >
            <div class='render-metric-name'>{this.data.alias || this.data.metric_name}</div>
          </bk-checkbox>
          <bk-popover
            ref='popoverRef'
            tippyOptions={{
              placement: 'bottom-start',
              distance: 8,
              theme: 'light edit-metric-alias-name',
              trigger: 'click',
              hideOnClick: true,
              zIndex: 99999,
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
                <bk-form
                  ref='fromRef'
                  form-type='vertical'
                  {...{
                    props: {
                      model: this.formData,
                      rules: this.formRules,
                    },
                  }}
                >
                  <bk-form-item
                    class='alias-item-label'
                    label={this.$t('指标别名：')}
                    property='description'
                  >
                    <bk-input
                      ref='inputRef'
                      v-model={this.formData.description}
                    />
                  </bk-form-item>
                </bk-form>
              </div>
              <div class='footer'>
                <bk-button
                  loading={this.isSubmiting}
                  theme='primary'
                  onClick={this.handleSubmit}
                >
                  {this.$t('确定')}
                </bk-button>
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
        <div slot='content'>
          <div>
            {this.$t('指标名：')}
            {this.data.metric_name}
          </div>
          <div>
            {this.$t('指标别名：')}
            {this.data.alias || '--'}
          </div>
        </div>
      </bk-popover>
    );
  }
}
