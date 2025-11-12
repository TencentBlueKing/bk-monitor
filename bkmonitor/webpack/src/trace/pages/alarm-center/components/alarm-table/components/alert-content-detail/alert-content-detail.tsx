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
import { type PropType, defineComponent, shallowRef } from 'vue';

import { Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import PromqlEditor from '../../../../../../components/promql-editor/promql-editor';
import QueryConfigViewer from '../query-config-viewer/query-config-viewer';

import type { AlertContentItem } from '../../../../typings';

import './alert-content-detail.scss';

export default defineComponent({
  name: 'AlertMetricsConfig',
  props: {
    alertContentDetail: {
      type: Object as PropType<AlertContentItem>,
    },
  },
  setup(props) {
    const { t } = useI18n();

    /** 当前是否为编辑状态 */
    const isEdit = shallowRef(false);
    /** 数据含义 input 框中的值 */
    const inputValue = shallowRef('');

    /**
     * @description: 切换编辑状态
     */
    function toggleEditMode(editStatus: boolean) {
      let value = '';
      if (editStatus) {
        value = props.alertContentDetail?.name || '';
      }
      inputValue.value = value;
      isEdit.value = editStatus;
    }

    /**
     * @description: 保存指标数据含义
     */
    function handleSave() {
      console.log('指标数据含义保存逻辑-----------------');
      toggleEditMode(false);
    }

    return {
      t,
      isEdit,
      inputValue,
      toggleEditMode,
      handleSave,
    };
  },
  render() {
    return (
      <div class='alert-content-detail'>
        <div class='description-meaning'>
          <div class='item-label'>
            <span>{`${this.t('数据含义')} :`}</span>
          </div>
          {this.isEdit ? (
            <div class='item-value-edit'>
              <Input
                v-model={this.inputValue}
                size='small'
              />
              <div class='operations'>
                <i
                  class='icon-monitor icon-mc-check-small'
                  onClick={this.handleSave}
                />
                <i
                  class='icon-monitor icon-mc-close'
                  onClick={() => this.toggleEditMode(false)}
                />
              </div>
            </div>
          ) : (
            <div class='item-value-view'>
              <span class='value'>{this.alertContentDetail?.name || '--'}</span>
              <i
                class='icon-monitor icon-bianji'
                onClick={() => this.toggleEditMode(true)}
              />
            </div>
          )}
        </div>
        {this.alertContentDetail?.origin_sql ? (
          <PromqlEditor
            class='alert-content-promql-view'
            readonly={true}
            value={this.alertContentDetail?.origin_sql}
          />
        ) : (
          <QueryConfigViewer
            expression={this.alertContentDetail?.expression}
            queryConfigs={this.alertContentDetail?.query_configs}
          />
        )}
      </div>
    );
  },
});
