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
import { defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

export default defineComponent({
  props: {
    status: {
      type: String,
      default: '',
    },
  },
  setup() {
    const { t } = useI18n();
    const eventStatusMap = {
      ABNORMAL: {
        color: '#EA3536',
        bgColor: '#FEEBEA',
        name: t('未恢复'),
        icon: 'icon-mind-fill',
      },
      RECOVERING: {
        color: '#FFB848',
        icon: 'icon-mc-visual',
        name: t('观察中'),
        bgColor: '#FFF3E1',
      },
      RECOVERED: {
        icon: 'icon-mc-check-fill',
        color: '#14A568',
        bgColor: '#E4FAF0',
        name: t('已恢复'),
      },
      CLOSED: {
        color: '#C4C6CC',
        bgColor: '#F5F7FA',
        icon: 'icon-mc-solved',
        name: t('已失效'),
      },
    };
    return {
      eventStatusMap,
    };
  },
  render() {
    const { status } = this;
    return (
      <div class='status-wrap'>
        <span
          style={{
            color: this.eventStatusMap?.[status]?.color,
            backgroundColor: this.eventStatusMap?.[status]?.bgColor,
          }}
          class='status-label'
        >
          {this.eventStatusMap?.[status]?.icon ? (
            <i
              style={{ color: this.eventStatusMap?.[status]?.color }}
              class={['icon-monitor item-icon', this.eventStatusMap?.[status]?.icon ?? '']}
            />
          ) : (
            ''
          )}
          {this.eventStatusMap?.[status]?.name || '--'}
        </span>
      </div>
    );
  },
});
