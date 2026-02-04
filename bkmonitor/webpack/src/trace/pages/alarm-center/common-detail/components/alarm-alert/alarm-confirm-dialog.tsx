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
import { defineComponent, shallowRef, watch } from 'vue';
import type { PropType } from 'vue';

import { Alert, Button, Dialog, Input, Loading, Message } from 'bkui-vue';
import { getActionConfigByAlerts } from 'monitor-api/modules/action';
import { ackAlert } from 'monitor-api/modules/alert_v2';
import { useI18n } from 'vue-i18n';

import './alarm-confirm-dialog.scss';

export default defineComponent({
  name: 'AlarmConfirm',
  props: {
    alarmBizId: {
      type: Number,
    },
    alarmIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'update:show': (value: boolean) => typeof value === 'boolean',
    confirm: (value: boolean) => typeof value === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const loading = shallowRef(false);
    /** 备注信息 */
    const content = shallowRef('');
    /** 关联套餐信息 */
    const infoContent = shallowRef([]);

    watch(
      () => props.show,
      val => {
        if (val) {
          getInfoData();
        }
      }
    );

    // 获取关联的套餐信息
    const getInfoData = () => {
      loading.value = true;
      getActionConfigByAlerts({
        alert_ids: props.alarmIds,
        bk_biz_id: props.alarmBizId,
      })
        .then(data => {
          infoContent.value = data
            .reduce((total, item) => {
              if (item.action_configs?.length) {
                return [...total, ...item.action_configs];
              }
              return total;
            }, [])
            .filter((item, index, arr) => arr.map(a => a.id).indexOf(item.id, 0) === index); // 去重
        })
        .finally(() => {
          loading.value = false;
        });
    };

    // 确认告警
    const handleAlarmConfirm = async () => {
      loading.value = true;
      const params = {
        ids: props.alarmIds,
        bk_biz_id: props.alarmBizId,
        message: content.value,
      };
      const res = await ackAlert(params).finally(() => {
        loading.value = false;
      });
      if (res) {
        let msg = {
          theme: 'success',
          message: t('告警确认成功'),
        };
        if (res.alerts_ack_success.length) {
          msg = {
            theme: 'success',
            message: t('告警确认成功'),
          };
          handleConfirm(true);
          handleShowChange(false);
        } else {
          msg = {
            theme: 'error',
            message: t('所有告警已恢复/关闭，无需确认'),
          };
        }
        Message(msg);
      }
    };

    const handleToMeal = (id: number) => {
      window.open(location.href.replace(location.hash, `#/set-meal/${id}`));
    };

    const handleConfirm = (val: boolean) => {
      emit('confirm', val);
    };

    const handleShowChange = (val: boolean) => {
      emit('update:show', val);
    };

    return {
      t,
      loading,
      content,
      infoContent,
      handleShowChange,
      handleToMeal,
      handleAlarmConfirm,
    };
  },
  render() {
    return (
      <Dialog
        width={480}
        v-slots={{
          default: () => (
            <Loading loading={this.loading}>
              <div class='alarm-confirm-dialog'>
                <Alert
                  class='info-tips'
                  v-slots={{
                    title: () => (
                      <div class='info-title'>
                        <div>{`${this.t('当该告警确认需要处理，并且希望该告警不再通知时，可以直接进行告警确认')}。`}</div>
                        <div>
                          {`${this.t('注意')}：${this.t(
                            '告警确认不会影响其他告警，只是避免当前告警的周期间隔发送和处理套餐的执行'
                          )}。`}
                        </div>
                      </div>
                    ),
                  }}
                  theme='info'
                />
                {this.infoContent.length
                  ? [
                      <div
                        key='title'
                        class='info-content-title'
                      >
                        {this.t('关联的处理套餐')}
                      </div>,
                      <div
                        key='content'
                        class='info-content'
                      >
                        {this.infoContent.map(item => (
                          <div
                            key={item.id}
                            class='lint-item'
                          >
                            <span
                              class='item-name'
                              onClick={() => this.handleToMeal(item.id)}
                            >
                              {item.name}
                              {this.t('套餐')}
                            </span>
                            <span class='item-id'>{`(#${item.id})`}</span>
                          </div>
                        ))}
                      </div>,
                    ]
                  : undefined}
                <Input
                  class='alarm-config-content'
                  v-model={this.content}
                  placeholder={this.t('填写告警确认备注信息')}
                  rows={5}
                  type='textarea'
                />
              </div>
            </Loading>
          ),
          footer: () => (
            <div class='footer-btns'>
              <Button
                style='margin-right: 10px'
                disabled={this.loading}
                theme='primary'
                onClick={this.handleAlarmConfirm}
              >
                {this.t('确认')}
              </Button>
              <Button onClick={() => this.handleShowChange(false)}>{this.t('取消')}</Button>
            </div>
          ),
        }}
        header-position={'left'}
        isShow={this.show}
        title={this.t('告警确认')}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
