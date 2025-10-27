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

import { defineComponent, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

export default defineComponent({
  name: 'TaskStatusDetail',
  props: {
    statusData: {
      type: Array,
      default() {
        return [];
      },
    },
  },
  setup(props) {
    const { t } = useLocale();

    // 成功状态列表
    const successState = ref(['CREATED', 'RUNNING', 'FINISHED']);

    // 计算耗时
    const calculateDuration = (row: any) => {
      if (row.finish_time) {
        return (new Date(row.finish_time).getTime() - new Date(row.start_time).getTime()) / 1000;
      }
      return '--';
    };

    // 表头渲染函数
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    return () =>
      props.statusData &&
      (props.statusData as any[]).length && (
        <div class='list-box-container'>
          {/* 标题 */}
          <div class='list-title'>
            <span class='bk-icon icon-exclamation-circle' />
            <h2 class='text'>{t('任务状态')}</h2>
          </div>

          {/* 表格 */}
          <bk-table data={props.statusData}>
            {/* 步骤列 */}
            <bk-table-column
              label={t('步骤')}
              prop='name_display'
              renderHeader={renderHeader}
            />

            {/* 开始时间列 */}
            <bk-table-column
              width='150'
              label={t('开始时间')}
              prop='start_time'
              renderHeader={renderHeader}
            />

            {/* 耗时列 */}
            <bk-table-column
              width='100'
              scopedSlots={{
                default: ({ row }: any) => <span>{calculateDuration(row)}</span>,
              }}
              label={t('耗时(s)')}
              renderHeader={renderHeader}
            />

            {/* 执行情况列 */}
            <bk-table-column
              scopedSlots={{
                default: ({ row }: any) => (
                  <div>
                    <span
                      class={[
                        'bk-icon',
                        successState.value.includes(row.state) ? 'icon-check-circle' : 'icon-close-circle',
                      ]}
                    />
                    <span>{row.state_display}</span>
                  </div>
                ),
              }}
              label={t('执行情况')}
              prop='state_display'
              renderHeader={renderHeader}
            />
          </bk-table>
        </div>
      );
  },
});
