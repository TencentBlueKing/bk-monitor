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
import dayjs from 'dayjs';
import { searchAlert } from 'monitor-api/modules/alert';
import { useI18n } from 'vue-i18n';

import { handleToAlertList, queryString } from '../../../utils';
import { AlarmLevelIconMap, AlertDataTypeMap } from '@/pages/alarm-center/typings';

import type { ActionDetail } from '../../../typings/action-detail';

export default defineComponent({
  name: 'ActionDetailContent',
  props: {
    detail: {
      type: Object as PropType<ActionDetail>,
      default: null,
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
        cell: (_h, { row }) => {
          const rectColor = AlarmLevelIconMap?.[row?.severity]?.iconColor;
          return (
            <div class='explore-col lever-rect-col'>
              <i
                style={{ '--lever-rect-color': rectColor }}
                class='lever-rect'
              />
              <div class='lever-rect-text ellipsis-text'>
                <span>{row?.alert_name}</span>
              </div>
            </div>
          );
        },
      },
      {
        colKey: 'alert_name',
        title: t('告警名称'),
      },
      {
        colKey: 'severity',
        title: t('告警级别'),
      },
      {
        colKey: 'description',
        title: t('告警内容'),
        cell: (_h, { row }) => {
          const item = { prefixIcon: AlertDataTypeMap[row.data_type]?.prefixIcon, alias: row.description };
          return (
            <div class='explore-col explore-prefix-icon-col alert-description-col'>
              <i class={`prefix-icon ${item?.prefixIcon}`} />
              <div class='ellipsis description-click'>
                <span>{item.alias || '--'}</span>
              </div>
            </div>
          );
        },
      },
    ];

    watch(
      () => props.detail,
      val => {
        if (val) {
          init();
        }
      }
    );

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
        <div class='trigger-alarm'>
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
      </div>
    );
  },
});
