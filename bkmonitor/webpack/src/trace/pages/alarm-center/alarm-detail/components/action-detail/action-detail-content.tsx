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

import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { Message, Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { searchAlert } from 'monitor-api/modules/alert_v2';
import { useI18n } from 'vue-i18n';

import { handleToAlertList, queryString } from '../../../utils';
import TableSkeleton from '@/components/skeleton/table-skeleton';
import AlertContentDetail from '@/pages/alarm-center/components/alarm-table/components/alert-content-detail/alert-content-detail';
import { saveAlertContentName } from '@/pages/alarm-center/services/alert-services';
import { AlarmLevelIconMap, AlertDataTypeMap } from '@/pages/alarm-center/typings';

import type { ActionDetail } from '../../../typings/action-detail';

import './action-detail-content.scss';

export default defineComponent({
  name: 'ActionDetailContent',
  props: {
    detail: {
      type: Object as PropType<ActionDetail>,
      default: null,
    },
    detailLoading: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const loading = shallowRef(false);
    const triggerTableData = shallowRef([]);
    const defenseTableData = shallowRef([]);

    const init = async () => {
      loading.value = true;
      const oneDay = 60 * 24 * 60;
      const params = {
        conditions: [],
        end_time: props.detail.end_time || dayjs.tz().unix(),
        ordering: [],
        page: 1,
        page_size: 10,
        record_history: false,
        show_aggs: false,
        show_overview: false,
        start_time: props.detail.create_time - oneDay,
        bk_biz_ids: [props.detail.bk_biz_id],
      };
      const triggerData = await searchAlert({
        ...params,
        query_string: `${queryString('trigger', props.detail.id)}`,
      }).catch(() => []);
      const defense = await searchAlert({
        ...params,
        query_string: `${queryString('defense', props.detail.id)}`,
      }).catch(() => []);
      triggerTableData.value = triggerData.alerts;
      defenseTableData.value = defense.alerts;
      loading.value = false;
    };

    const columns = [
      {
        colKey: 'id',
        title: t('告警ID'),
        width: 200,
        cell: (_h, { row }) => {
          return (
            <div class='ellipsis'>
              <span>{row?.id}</span>
            </div>
          );
        },
      },
      {
        colKey: 'alert_name',
        title: t('告警名称'),
        cell: (_h, { row }) => {
          const rectColor = AlarmLevelIconMap?.[row?.severity]?.iconColor;
          return (
            <div
              style={{ borderLeftColor: rectColor }}
              class='alarm-name-col ellipsis'
            >
              <span>{row?.alert_name}</span>
            </div>
          );
        },
      },
      {
        colKey: 'severity',
        title: t('告警级别'),
        width: 100,
        cell: (_h, { row }) => {
          const level = AlarmLevelIconMap?.[row?.severity];
          return (
            <div
              style={{ borderLeftColor: level?.iconColor, color: level.textColor }}
              class='alarm-level-col'
            >
              {level?.text || '--'}
            </div>
          );
        },
      },
      {
        colKey: 'description',
        title: t('告警内容'),
        cell: (_h, { row }) => {
          const item = { prefixIcon: AlertDataTypeMap[row.data_type]?.prefixIcon, alias: row.description };
          return (
            <div class='alarm-content-col'>
              <i class={`prefix-icon ${item?.prefixIcon}`} />
              <Popover
                width={480}
                extCls='alarm-alert-monitor-data-popover'
                v-slots={{
                  default: () => (
                    <div class='ellipsis description-click'>
                      <span>{item.alias || '--'}</span>
                    </div>
                  ),
                  content: () => (
                    <div class='alarm-alert-monitor-data-popover-content'>
                      <AlertContentDetail
                        alertContentDetail={row?.items?.[0]}
                        alertId={row?.id}
                        bizId={row?.bk_biz_id}
                        onSave={(saveInfo, savePromiseEvent) => handleSaveContentName(saveInfo, savePromiseEvent)}
                      />
                    </div>
                  ),
                }}
                placement='bottom'
                theme='light'
                trigger='click'
              />
            </div>
          );
        },
      },
    ];

    watch(
      () => props.detail,
      val => {
        if (val && !props.detailLoading) {
          init();
        }
      },
      {
        immediate: true,
      }
    );

    /**
     * @description 保存告警内容数据含义
     * @param {AlertContentNameEditInfo} saveInfo 保存信息
     * @param {AlertSavePromiseEvent} savePromiseEvent 保存事件
     */
    const handleSaveContentName = (saveInfo, savePromiseEvent) => {
      saveAlertContentName(saveInfo)
        .then(() => {
          savePromiseEvent?.successCallback?.();
          const targetRow = [...defenseTableData.value, ...triggerTableData.value].find(
            item => item.id === saveInfo.alert_id
          );
          const alertContent = targetRow?.items?.[0];
          if (alertContent) {
            alertContent.name = saveInfo.data_meaning;
          }
          Message({
            message: t('更新成功'),
            theme: 'success',
          });
        })
        .catch(() => {
          savePromiseEvent?.errorCallback?.();
          Message({
            message: t('更新失败'),
            theme: 'error',
          });
        });
    };

    const handleJump = (type: 'defense' | 'trigger') => {
      const { create_time: createTime, end_time: endTime, id, converge_id: convergeId } = props.detail;
      handleToAlertList(
        type,
        { create_time: createTime, end_time: endTime, id, converge_id: convergeId },
        props.detail.bk_biz_id
      );
    };

    return {
      loading,
      triggerTableData,
      defenseTableData,
      columns,
      handleJump,
    };
  },
  render() {
    return (
      <div class='action-detail-content'>
        {this.loading && (
          <div class='skeleton-wrapper'>
            <div class='alarm-table'>
              <div class='skeleton-element alarm-table-title' />
              <TableSkeleton />
            </div>
          </div>
        )}

        {!this.loading && this.triggerTableData.length > 0 && (
          <div class='trigger-alarm alarm-table'>
            <div class='alarm-table-title'>
              <span class='title'>{this.$t('触发的告警')}</span>
              <i18n-t
                class='msg'
                keypath='仅展示最近10条，更多详情请{0}'
                tag='span'
              >
                <span
                  class='table-title-link'
                  onClick={() => this.handleJump('trigger')}
                >
                  <span class='link-text'>{this.$t('前往告警列表')}</span>
                </span>
              </i18n-t>
            </div>

            <PrimaryTable
              columns={this.columns}
              data={this.triggerTableData}
            />
          </div>
        )}

        {!this.loading && this.defenseTableData.length > 0 && (
          <div class='defense-alarm alarm-table'>
            <div class='alarm-table-title'>
              <span class='title'>{this.$t('防御的告警')}</span>
              <i18n-t
                class='msg'
                keypath='仅展示最近10条，更多详情请{0}'
                tag='span'
              >
                <span
                  class='table-title-link'
                  onClick={() => this.handleJump('defense')}
                >
                  <span class='link-text'>{this.$t('前往告警列表')}</span>
                </span>
              </i18n-t>
            </div>

            <PrimaryTable
              columns={this.columns}
              data={this.defenseTableData}
            />
          </div>
        )}
      </div>
    );
  },
});
