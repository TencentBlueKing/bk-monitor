/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { type PropType, computed, defineComponent } from 'vue';

import { Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { ITableFilterItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './status-tab.scss';

const IProps = {
  value: {
    type: String,
    required: false,
  },
  needAll: {
    type: Boolean,
    required: false,
  },
  statusList: {
    type: Array as PropType<ITableFilterItem[]>,
  },
  disabledClickZero: {
    type: Boolean,
    required: false,
  },
};

export default defineComponent({
  name: 'StatusTab',
  props: IProps,
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const defaultList = [
      {
        id: 'all',
        name: t('全部'),
      },
    ];

    const localStatusList = computed<ITableFilterItem[]>(() => [
      ...(props.needAll ? defaultList : []),
      ...props.statusList,
    ]);

    /** 点击选中 */
    const handleClickItem = (item: ITableFilterItem) => {
      if (item.name === 0 && props.disabledClickZero) {
        return;
      }
      emit('change', item.id);
    };

    return {
      handleClickItem,
      localStatusList,
    };
  },
  render() {
    const { value } = this.$props;
    const getContent = (item: ITableFilterItem, isLastInex: boolean) => (
      <span
        class={['common-status-wrap status-tab-item', { active: value === item.id, 'is-last-item': isLastInex }]}
        onClick={() => this.handleClickItem(item)}
      >
        {item.status && <span class={['common-status-icon', `status-${item.status}`]} />}
        {item.icon && <i class={['icon-monitor', item.icon]} />}
        {(!!item.name || item.name === 0) && (
          <span class={['status-count', { 'plain-text': !item.icon }]}>{item.name}</span>
        )}
      </span>
    );

    return (
      <div class='status-tab-wrap'>
        {this.localStatusList.map((item, index) => (
          <Popover
            key={index}
            boundary='parent'
            content={item.tips}
            disabled={!item.tips}
            placement='bottom'
            theme='light'
          >
            {getContent(item, index === this.localStatusList.length - 1)}
          </Popover>
        ))}
      </div>
    );
  },
});
