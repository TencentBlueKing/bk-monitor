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

import { computed, defineComponent, ref } from 'vue';

import { xssFilter } from '@/common/util';
import useLocale from '@/hooks/use-locale';

import { contents } from '../create-operation/log';

import './host-detail.scss';

export default defineComponent({
  name: 'HostDetail',
  props: {
    log: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: [''],

  setup(props, { emit }) {
    const { t } = useLocale();
    const activeKey = ref('all');
    const itemKey = ref(2000058532);
    const tabList = computed(() => [
      {
        key: 'all',
        label: t('全部'),
        count: 1,
      },
      {
        key: 'success',
        label: t('成功'),
        count: 1,
      },
      {
        key: 'failed',
        label: t('失败'),
        count: 1,
      },
      {
        key: 'running',
        label: t('执行中'),
        count: 0,
      },
    ]);

    const handleTabClick = item => {
      if (item.count !== 0) {
        activeKey.value = item.key;
      }
    };

    const handleItemClick = item => {
      console.log(item);
      itemKey.value = item.host_id;
    };

    return () => (
      <div class='host-detail-main'>
        <span class='host-detail-tab'>
          {tabList.value.map(item => (
            <span
              key={item.key}
              class={{
                'host-detail-tab-item': true,
                active: activeKey.value === item.key,
                disabled: item.count === 0,
              }}
              on-click={() => handleTabClick(item)}
            >
              {['success', 'failed'].includes(item.key) && <span class={`item-circle ${item.key}`} />}
              {item.key === 'running' && <i class='running' />}
              {item.label} （{item.count}）
            </span>
          ))}
        </span>
        <div class='host-detail-content'>
          <div class='content-left'>
            <div class='content-left-title'>{t('主机')}</div>
            <div class='left-list'>
              {contents[0].child.map(item => (
                <div
                  key={item.host_id}
                  class={{ 'left-item': true, active: itemKey.value === item.host_id }}
                  on-click={() => handleItemClick(item)}
                >
                  {item.status === 'running' ? <i class='running' /> : <span class={`item-circle ${item.status}`} />}
                  {item.ip}
                </div>
              ))}
            </div>
          </div>
          <div class='content-right'>
            <div class='content-right-title'>
              <i class={`bklog-icon bklog-circle-correct-filled status-icon ${props.log.log_result.status}`} />
              {t('采集详情 ')}
              <i class='bklog-icon bklog-refresh2 refresh-icon' />
            </div>
            <div
              class='content-box'
              domPropsInnerHTML={xssFilter(props.log?.log_detail ?? '')}
            />
          </div>
        </div>
      </div>
    );
  },
});
