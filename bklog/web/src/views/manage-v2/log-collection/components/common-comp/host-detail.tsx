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

import { computed, defineComponent, ref, watch, type PropType } from 'vue';

import { xssFilter } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { showMessage } from '../../utils';
import $http from '@/api';

import './host-detail.scss';

type IHostItem = {
  host_id: number;
  instance_id: string;
  task_id: string;
  ip: string;
  status: string;
  [key: string]: any;
};

type ILogItem = {
  bk_obj_id: string;
  bk_obj_name: string;
  child: IHostItem[];
  [key: string]: any;
};

export default defineComponent({
  name: 'HostDetail',
  props: {
    loading: {
      type: Boolean,
      default: false,
    },
    list: {
      type: Array as PropType<ILogItem[]>,
      default: () => [],
    },
    tabList: {
      type: Array as PropType<{ key: string; label: string; count: number }[]>,
      default: () => [],
    },
  },

  setup(props) {
    const { t } = useLocale();
    const store = useStore();
    const activeKey = ref('all');
    const currentItem = ref({});
    const itemLoading = ref(false);
    const log = ref('');
    const detail = ref({});
    const curCollect = computed(() => store.getters['collect/curCollect']);

    const showList = computed(() => {
      const list = props.list;
      if (activeKey.value === 'all') {
        return list;
      }
      return list.filter(item => {
        const childList = item.child.filter(child => child.status === activeKey.value);
        return childList.length > 0 && { ...item, child: childList };
      });
    });

    /**
     * 切换tab的时候默认选中第一个item
     */
    const setDefaultItem = () => {
      if (showList.value.length === 0) {
        return;
      }
      const firstItem = showList.value[0].child[0];
      handleItemClick(firstItem);
    };
    /**
     * 切换Tab
     * @param item
     */
    const handleTabClick = item => {
      if (item.count !== 0) {
        log.value = '';
        detail.value = {};
        activeKey.value = item.key;
      }
    };
    /**
     * 获取选中的ip详情
     * @param item
     */
    const getItemDetail = item => {
      itemLoading.value = true;
      $http
        .request('collect/executDetails', {
          params: {
            collector_id: curCollect.value.collector_config_id,
          },
          query: {
            instance_id: item.instance_id,
            task_id: item.task_id,
          },
        })
        .then(res => {
          if (res.result) {
            log.value = res.data.log_detail;
            detail.value = res.data.log_result;
          }
        })
        .catch(err => {
          showMessage(err.message || err, 'error');
        })
        .finally(() => {
          itemLoading.value = false;
        });
    };
    /**
     * 选择某个ip
     * @param item
     */
    const handleItemClick = item => {
      currentItem.value = item;
      getItemDetail(item);
    };

    const renderIcon = () => {
      const statusIconMap = {
        SUCCESS: 'bklog-circle-correct-filled',
        FAILED: 'bklog-circle-alert-filled',
      };
      const iconClass = statusIconMap[detail.value.status];
      return iconClass ? <i class={`bklog-icon ${iconClass} status-icon ${detail.value.status}`} /> : null;
    };

    watch(
      () => props.loading,
      val => {
        !val && setDefaultItem();
      },
    );

    watch(
      () => activeKey.value,
      () => {
        setDefaultItem();
      },
      {
        immediate: true,
      },
    );

    return () => (
      <div class='host-detail-main'>
        <span class='host-detail-tab'>
          {props.tabList.map(item => (
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
        <div v-bkloading={{ isLoading: props.loading }}>
          {showList.value.length === 0 ? (
            <bk-exception
              class='host-detail-main-empty'
              scene='part'
              type='empty'
            />
          ) : (
            <div class='host-detail-content'>
              <div class='content-left'>
                {showList.value.map(logItem => (
                  <div
                    key={logItem.bk_obj_id}
                    class='detail-content-item'
                  >
                    <div class='content-left-title'>{logItem.bk_obj_name}</div>
                    <div class='left-list'>
                      {logItem.child.map(item => (
                        <div
                          key={item.host_id}
                          class={{ 'left-item': true, active: currentItem.value.host_id === item.host_id }}
                          on-click={() => handleItemClick(item)}
                        >
                          {item.status === 'running' ? (
                            <i class='running' />
                          ) : (
                            <span class={`item-circle ${item.status}`} />
                          )}
                          {item.ip}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div class='content-right'>
                <div class='content-right-title'>
                  {renderIcon()}
                  {t('采集详情 ')}
                  <i
                    class='bklog-icon bklog-refresh2 refresh-icon'
                    on-click={() => getItemDetail(currentItem.value)}
                  />
                </div>
                <div
                  class='content-right-detail'
                  v-bkloading={{ isLoading: itemLoading.value, color: '#2E2E2E', zIndex: 10 }}
                >
                  <div
                    class='content-box'
                    domPropsInnerHTML={xssFilter(log.value || '')}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  },
});
