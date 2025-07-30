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
import { type PropType, defineComponent, ref, toRefs, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import IconFont from '../icon-font/icon-font';
import SelectMenu, { type ISelectMenuOption } from '../select-menu/select-menu';

import './refresh-rate.scss';
/**
 * 自定义触发目标的选择菜单组件
 */
const IProps = {
  list: {
    type: Array as PropType<ISelectMenuOption[]>,
    default: () => [
      // 刷新间隔列表
      {
        name: `${window.i18n.t('关闭')}（off）`,
        id: -1,
      },
      {
        name: '1m',
        id: 60 * 1000,
      },
      {
        name: '5m',
        id: 5 * 60 * 1000,
      },
      {
        name: '15m',
        id: 15 * 60 * 1000,
      },
      {
        name: '30m',
        id: 30 * 60 * 1000,
      },
      {
        name: '1h',
        id: 60 * 60 * 1000,
      },
      {
        name: '2h',
        id: 60 * 2 * 60 * 1000,
      },
      {
        name: '1d',
        id: 60 * 24 * 60 * 1000,
      },
    ],
  },
  value: {
    /** 选中值 */ type: Number,
    default: -1,
  },
  onSelect: {
    /** 选中的事件 */ type: Function as PropType<(item: number) => void>,
  },
  onImmediate: {
    /** 立即刷新 */ type: Function as PropType<() => void>,
  },
};
/**
 * 图表的刷新频率组件
 */
export default defineComponent({
  name: 'RefreshRate',
  props: IProps,
  setup(props, { emit }) {
    const { list, value } = toRefs(props);
    const { t } = useI18n();

    /** 选中的值 */
    const localValue = ref(value.value);

    /** 菜单展示状态 */
    const isShow = ref(false);

    /** 更新本地选中值 */
    watch(
      value,
      val => {
        localValue.value = val;
      },
      { immediate: true }
    );

    /** 选中值 */
    const handleSelect = (item: ISelectMenuOption) => {
      localValue.value = item.id as number;
      emit('update:value', localValue.value);
      emit('select', localValue.value);
    };

    /**
     * 点击立即刷新
     */
    const handeRefreshImmediately = (evt: Event) => {
      evt.stopPropagation();
      emit('immediate');
    };
    return {
      list,
      localValue,
      isShow,
      handleSelect,
      handeRefreshImmediately,
      t,
    };
  },
  render() {
    const textActive = this.localValue !== -1;

    return (
      <span class='refresh-rate-wrap'>
        <SelectMenu
          v-slots={{
            default: item => {
              let triggerText = item?.name || this.list[0].name;
              if (triggerText === `${this.t('关闭')}（off）`) {
                triggerText = 'off';
              }

              return (
                <span class='refresh-rate-main'>
                  <div class='trigger-name'>
                    <IconFont
                      classes={['icon-refresh']}
                      icon={'icon-zidongshuaxin'}
                    />
                    <span class={['refresh-text', { 'active-text': textActive }]}>{triggerText}</span>
                  </div>
                  <IconFont
                    fontSize={16}
                    icon='icon-mc-alarm-recovered'
                    onClick={this.handeRefreshImmediately}
                  />
                </span>
              );
            },
          }}
          list={this.list}
          value={this.localValue}
          onSelect={this.handleSelect}
          onShowChange={val => (this.isShow = val)}
        />
      </span>
    );
  },
});
