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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listUserGroup } from 'monitor-api/modules/model';

import Threshold from './detect-rules/threshold';
import { type TemplateDetail, TemplateTypeMap } from './typing';

import './template-form.scss';

interface TemplateFormEvents {
  onChange(data: TemplateDetail): void;
}

interface TemplateFormProps {
  data: TemplateDetail;
  scene: 'edit' | 'view';
}

@Component
export default class TemplateForm extends tsc<TemplateFormProps, TemplateFormEvents> {
  @Prop({ default: 'edit' }) scene: 'edit' | 'view';
  @Prop({ default: () => ({}) }) data: TemplateDetail;

  alarmGroupLoading = false;

  alarmGroupList = [];

  get monitorData() {
    if (this.data?.query_template?.alias) {
      return `${this.data.query_template.alias}(${this.data.query_template.name})`;
    }
    return this.data?.query_template?.name;
  }

  get selectUserGroup() {
    return this.data?.user_group_list?.map(item => item.id) || [];
  }

  handleChangeAutoApply(value: boolean) {}

  // 获取告警组数据
  getAlarmGroupList() {
    this.alarmGroupLoading = true;
    return listUserGroup({ exclude_detail_info: 1 })
      .then(data => {
        this.alarmGroupList = data.map(item => ({
          id: item.id,
          name: item.name,
          needDuty: item.need_duty,
          receiver:
            item?.users?.map(rec => rec.display_name).filter((item, index, arr) => arr.indexOf(item) === index) || [],
        }));
      })
      .finally(() => {
        this.alarmGroupLoading = false;
      });
  }

  mounted() {
    this.getAlarmGroupList();
  }

  render() {
    return (
      <bk-form
        class='template-form'
        label-width={122}
      >
        <bk-form-item label={this.$tc('监控数据')}>
          <span class='text'>{this.monitorData}</span>
        </bk-form-item>
        <bk-form-item
          class='mt16'
          label={this.$tc('模板类型')}
        >
          <span class='text'>{TemplateTypeMap[this.data?.system]}</span>
        </bk-form-item>
        <bk-form-item
          class='mt16'
          label={this.$tc('模板名称')}
          required
        >
          {this.scene === 'edit' ? <bk-input value={this.data?.name} /> : <span>{this.data?.name}</span>}
        </bk-form-item>
        <bk-form-item
          class='mt24'
          label={this.$tc('检测规则')}
          required
        >
          <Threshold data={this.data?.algorithms} />
        </bk-form-item>
        <bk-form-item
          class='mt24'
          label={this.$tc('判断条件')}
          required
        >
          <i18n path='在{0}个周期内累计满足{1}次检测算法'>
            <bk-input
              class='small-input'
              behavior='simplicity'
              show-controls={false}
              size='small'
              type='number'
              value={this.data?.detect?.trigger_check_window}
            />
            <bk-input
              class='small-input'
              behavior='simplicity'
              show-controls={false}
              size='small'
              type='number'
              value={this.data?.detect?.trigger_count}
            />
          </i18n>
        </bk-form-item>
        <bk-form-item
          class='mt24'
          label={this.$tc('告警组')}
          required
        >
          <bk-select
            loading={this.alarmGroupLoading}
            value={this.selectUserGroup}
            collapse-tag
            display-tag
            multiple
            searchable
          >
            {this.alarmGroupList.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            ))}
          </bk-select>
        </bk-form-item>

        <bk-form-item
          class='mt24'
          label={this.$tc('自动下发')}
        >
          <bk-switcher
            theme='primary'
            value={this.data.is_auto_apply}
            onChange={this.handleChangeAutoApply}
          />
        </bk-form-item>
      </bk-form>
    );
  }
}
