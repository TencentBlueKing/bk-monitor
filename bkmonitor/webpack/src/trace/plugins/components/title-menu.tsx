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
import { type PropType, defineComponent, getCurrentInstance, ref, watch } from 'vue';

import { Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { createMetricTitleTooltips } from '../../utils';

import type { ChartTitleMenuType, IExtendMetricData, IMenuChildItem, IMenuItem } from '../typings';

import './title-menu.scss';

export default defineComponent({
  name: 'TitleMenu',
  props: {
    list: {
      type: Array as PropType<ChartTitleMenuType[]>,
      default: () => ['save', 'screenshot', 'explore', 'set', 'area'],
    },
    drillDownOption: {
      type: Array as PropType<IMenuChildItem[]>,
      default: () => [],
    },
    metrics: {
      type: Array as PropType<IExtendMetricData[]>,
      default: () => [],
    },
    showAddMetric: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['select', 'metricSelect', 'selectChild', 'childMenuToggle'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const instance = getCurrentInstance();
    const menuList = ref<IMenuItem[]>([
      {
        name: t('保存到仪表盘'),
        checked: false,
        id: 'save',
        icon: 'mc-mark',
      },
      {
        name: t('截图到本地'),
        checked: false,
        id: 'screenshot',
        icon: 'mc-camera',
      },
      {
        name: t('查看大图'),
        checked: false,
        id: 'fullscreen',
        icon: 'fullscreen',
      },
      {
        name: t('检索'),
        checked: false,
        id: 'explore',
        icon: 'mc-retrieval',
        hasLink: true,
      },
      {
        name: t('下钻'),
        checked: false,
        id: 'drill-down',
        icon: 'xiazuan',
        hasLink: true,
        childValue: '',
        children: [],
      },
      {
        name: t('相关告警'),
        checked: false,
        id: 'relate-alert',
        icon: 'mc-menu-alert',
        hasLink: true,
      },
      {
        name: t('添加策略'),
        checked: false,
        id: 'strategy',
        icon: 'mc-strategy',
        hasLink: true,
      },
      {
        name: t('Y轴固定最小值为0'),
        checked: false,
        id: 'set',
        nextName: t('Y轴自适应'),
        icon: 'mc-yaxis',
        nextIcon: 'mc-yaxis-scale',
      },
      {
        name: t('更多'),
        checked: false,
        id: 'more',
        icon: 'gengduo',
        childValue: '',
        children: [
          {
            id: 'screenshot',
            name: t('截图到本地'),
            icon: 'mc-camera',
          },
          {
            id: 'export-csv',
            name: t('导出CSV'),
            icon: 'xiazai1',
          },
        ],
      },
    ]);
    watch(
      () => props.drillDownOption,
      () => {
        const drillDown = menuList.value.find(item => item.id === 'drill-down');
        if (drillDown) {
          /** 服务实例实例 | 主机 | 自定义上报target 优先级从左往右 */
          const defaultKeys = ['bk_target_service_instance_id', 'bk_target_ip', 'target'];
          const optionsKeys = props.drillDownOption.map(item => item.id);
          drillDown.childValue = optionsKeys[0] ?? '';
          for (const key of defaultKeys) {
            if (optionsKeys.includes(key)) {
              drillDown.childValue = key;
              break;
            }
          }
          drillDown.children = props.drillDownOption.map(item => ({
            ...item,
            needTips: true,
          }));
        }
      }
    );
    function handleMenuClick(item: IMenuItem) {
      emit('select', item);
    }
    /**
     * @description: 选择单个指标
     * @param {IExtendMetricData} metric
     * @return {*}
     */
    function handleMetricSelect(metric: IExtendMetricData) {
      emit('metricSelect', metric);
    }
    /**
     * 选中子菜单
     * @param item 菜单
     * @param val 子菜单值
     */
    function handleSelectChild(menu: IMenuItem, child: IMenuChildItem) {
      !!menu.childValue && (menu.childValue = child.id);
      const key = `${menu.id}-popover`;
      (instance?.refs[key] as any)?.hideHandler?.();
      emit('selectChild', {
        child,
        menu,
      });
    }
    function handleChildMenuToggle(val: boolean) {
      emit('childMenuToggle', val);
    }
    function handleGetItemName(options: IMenuChildItem[], id: string) {
      return options.find(item => item.id === id)?.name;
    }
    return {
      menuList,
      handleMenuClick,
      handleMetricSelect,
      handleSelectChild,
      handleChildMenuToggle,
      handleGetItemName,
    };
  },
  render() {
    return (
      <ul class='chart-menu'>
        {this.menuList.map(item => {
          const isHidden = !this.list.includes(item.id) || (item.id === 'drill-down' && !item.children?.length);
          if (isHidden) return undefined;
          /**
           * 子菜单
           */
          const childTpl = (item: IMenuItem) => (
            <ul class='child-list'>
              {item.children?.map(child => (
                <Popover
                  key={child.id}
                  content={child.id}
                  disabled={!child.needTips}
                  placement={'right'}
                >
                  <li
                    class={['child-list-item', { active: child.id === item.childValue }]}
                    onClick={() => this.handleSelectChild(item, child)}
                  >
                    {child.icon && <i class={`child-icon icon-monitor ${`icon-${child.icon}`}`} />}
                    {child.name}
                  </li>
                </Popover>
              ))}
            </ul>
          );
          /**
           * 一级菜单
           */
          const menuItemTpl = (
            <li
              key={item.id}
              class='chart-menu-item'
              onClick={() => this.handleMenuClick(item)}
            >
              <i class={`menu-icon icon-monitor ${`icon-${!item.checked ? item.icon : item.nextIcon || item.icon}`}`} />
              {!item.checked ? item.name : item.nextName || item.name}
              {!!item.children?.length && item.hasLink && (
                <Popover
                  ref={`${item.id}-popover`}
                  animation='slide-toggle'
                  arrow={false}
                  disabled={item.children.length < 2}
                  distance={12}
                  offset={-1}
                  placement='bottom-start'
                  theme='light cycle-list-wrapper child-list-popover'
                >
                  <span class='menu-item-trigger'>{this.handleGetItemName(item.children, item.childValue!)}</span>
                  {childTpl(item)}
                </Popover>
              )}
              {item.hasLink ? <i class='icon-monitor icon-mc-link link-icon' /> : undefined}
              {!item.hasLink && item.children?.length && <i class='icon-monitor icon-arrow-right more-icon' />}
            </li>
          );
          if (item.children?.length && !item.hasLink) {
            return (
              <Popover
                ref={`${item.id}-popover`}
                class='chart-menu-item-more'
                v-slots={{
                  default: () => menuItemTpl,
                  content: () => childTpl(item),
                }}
                arrow={false}
                offset={-1}
                placement='right-start'
                theme='light cycle-list-wrapper child-list-popover more'
              />
            );
          }
          return menuItemTpl;
        })}
        {this.showAddMetric &&
          this.metrics?.map((item, index) => (
            <li
              key={index}
              class={`chart-menu-item ${index === 0 ? 'segmentation-item' : ''}`}
              onClick={() => this.handleMetricSelect(item)}
            >
              <i class='icon-monitor icon-mc-add-strategy strategy-icon' />
              <span class='field-name'>{item.metric_field_name}</span>
              <Popover>
                {{
                  default: () => <i class='icon-monitor icon-hint tips-icon' />,
                  content: () => (
                    <div
                      class='common-chart-tooltips-wrap'
                      v-html={createMetricTitleTooltips(item)}
                    />
                  ),
                }}
              </Popover>
            </li>
          ))}
      </ul>
    );
  },
});
