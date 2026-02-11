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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { Button, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import PromqlEditor from '../../../../../../components/promql-editor/promql-editor';
import QueryConfigViewer from '../query-config-viewer/query-config-viewer';

import type { AlertContentItem, AlertContentNameEditInfo } from '../../../../typings';

import './alert-content-detail.scss';

export interface AlertSavePromiseEvent {
  /** 确认删除的 Promise */
  promiseEvent: Promise<any>;
  /** 失败回调 */
  errorCallback: () => void;
  /** 成功回调 */
  successCallback: () => void;
}

export default defineComponent({
  name: 'AlertMetricsConfig',
  props: {
    /** 业务 ID */
    bizId: {
      type: Number,
    },
    /** 告警 ID */
    alertId: {
      type: String,
    },
    /** 告警内容 */
    alertContentDetail: {
      type: Object as PropType<AlertContentItem>,
    },
  },
  emits: {
    save: (saveInfo: AlertContentNameEditInfo, savePromiseEvent: AlertSavePromiseEvent) => saveInfo && savePromiseEvent,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 当前是否为编辑状态 */
    const isEdit = shallowRef(false);
    /** 数据含义 input 框中的值 */
    const inputValue = shallowRef('');
    /** 是否在请求修改状态中 */
    const loading = shallowRef(false);

    /**
     * @description: 切换编辑状态
     * @param {Boolean} editStatus 数据含义是否处于编辑状态
     */
    const toggleEditMode = (editStatus: boolean) => {
      let value = '';
      if (editStatus) {
        value = props.alertContentDetail?.name || '';
      }
      inputValue.value = value;
      isEdit.value = editStatus;
    };

    /**
     * @description: 保存指标数据含义
     */
    const handleSave = () => {
      const saveName = inputValue.value?.trim?.() ?? '';
      if (!saveName || saveName === props.alertContentDetail?.name) {
        toggleEditMode(false);
        return;
      }
      loading.value = true;
      let successCallback = null;
      let errorCallback = null;
      const promiseEvent = new Promise((res, rej) => {
        successCallback = res;
        errorCallback = rej;
      })
        .then(() => {
          loading.value = false;
          toggleEditMode(false);
        })
        .catch(() => {
          loading.value = false;
        });

      emit(
        'save',
        {
          alert_id: props.alertId,
          data_meaning: saveName,
          bk_biz_id: props.bizId || (window.bk_biz_id as number) || (window.cc_biz_id as number),
        },
        {
          promiseEvent,
          successCallback,
          errorCallback,
        }
      );
    };

    watch(
      () => props.alertContentDetail,
      () => {
        toggleEditMode(false);
      }
    );

    return {
      t,
      isEdit,
      loading,
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
                disabled={this.loading}
                size='small'
              />
              <div class='operations'>
                <Button
                  loading={this.loading}
                  loading-mode='spin'
                  size='small'
                  text={true}
                  onClick={this.handleSave}
                >
                  <i class='icon-monitor icon-mc-check-small' />
                </Button>
                <Button
                  disabled={this.loading}
                  size='small'
                  text={true}
                  onClick={() => this.toggleEditMode(false)}
                >
                  <i class={`icon-monitor icon-mc-close ${this.loading ? 'is-disabled' : ''}`} />
                </Button>
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
            options={{ fontSize: 12 }}
            readonly={true}
            resizable={false}
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
