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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { createMetricTitleTooltips } from '../../utils';

import type { ChartTitleMenuType, IExtendMetricData, IMenuChildItem, IMenuItem } from '../../typings';

import './chart-title-menu.scss';

export interface IChartTitleMenuEvents {
  onChildMenuToggle: boolean;
  onMetricSelect?: IExtendMetricData;
  onSelect?: IMenuItem;
  onSelectChild: { child: IMenuChildItem; menu: IMenuItem };
}
interface IChartTitleProps {
  drillDownOption?: IMenuChildItem[];
  list: ChartTitleMenuType[];
  // 指标数据
  metrics?: IExtendMetricData[];
  // 是否显示添加指标到策略选项
  showAddMetric?: boolean;
  // 菜单是否展示
  showMenu?: boolean;
}
@Component
export default class ChartTitleMenu extends tsc<IChartTitleProps, IChartTitleMenuEvents> {
  @Prop({ default: () => ['save', 'screenshot', 'fullscreen', 'explore', 'set', 'area'] }) list: ChartTitleMenuType[];
  @Prop({ default: () => [] }) drillDownOption: IMenuChildItem[];
  @Prop({ default: () => [] }) metrics: IExtendMetricData[];
  @Prop({ type: Boolean, default: true }) showAddMetric: boolean;
  @Prop({ type: Boolean, default: true }) showMenu: boolean;
  menuList: IMenuItem[] = [];
  showMenuItem = false;
  currShowItemRef = '';
  created() {
    this.menuList = [
      {
        name: window.i18n.t('保存到仪表盘'),
        checked: false,
        id: 'save',
        icon: 'mc-mark',
      },
      {
        name: window.i18n.t('截图到本地'),
        checked: false,
        id: 'screenshot',
        icon: 'mc-camera',
      },
      {
        name: window.i18n.t('查看大图'),
        checked: false,
        id: 'fullscreen',
        icon: 'fullscreen',
      },
      {
        name: window.i18n.t('检索'),
        checked: false,
        id: 'explore',
        icon: 'mc-retrieval',
        hasLink: true,
      },
      {
        name: window.i18n.t('下钻'),
        checked: false,
        id: 'drill-down',
        icon: 'xiazuan',
        hasLink: true,
        childValue: '',
        children: [],
      },
      {
        name: window.i18n.t('相关告警'),
        checked: false,
        id: 'relate-alert',
        icon: 'mc-menu-alert',
        hasLink: true,
      },
      {
        name: window.i18n.t('添加策略'),
        checked: false,
        id: 'strategy',
        icon: 'mc-strategy',
        hasLink: true,
      },
      {
        name: window.i18n.t('Y轴固定最小值为0'),
        checked: false,
        id: 'set',
        nextName: window.i18n.t('Y轴自适应'),
        icon: 'mc-yaxis',
        nextIcon: 'mc-yaxis-scale',
      },
      {
        name: window.i18n.t('更多'),
        checked: false,
        id: 'more',
        icon: 'gengduo',
        // hasLink: true,
        childValue: '',
        children: [
          {
            id: 'screenshot',
            name: window.i18n.t('截图到本地'),
            icon: 'mc-camera',
          },
          {
            id: 'export-csv',
            name: window.i18n.t('导出CSV'),
            icon: 'xiazai1',
          },
        ],
      },
      // {
      //   name: window.i18n.t('面积图'),
      //   checked: false,
      //   id: 'area',
      //   nextName: window.i18n.t('线性图'),
      //   icon: 'mc-area',
      //   nextIcon: 'mc-line'
      // }
    ];
  }
  @Watch('drillDownOption', { deep: true })
  drillDownOptionChange() {
    const drillDown = this.menuList.find(item => item.id === 'drill-down');
    if (drillDown) {
      /** 服务实例实例 | 主机 | 自定义上报target 优先级从左往右 */
      const defaultKeys = ['bk_target_service_instance_id', 'bk_target_ip', 'target'];
      const optionsKeys = this.drillDownOption.map(item => item.id);
      drillDown.childValue = optionsKeys[0] ?? '';
      for (const key of defaultKeys) {
        if (optionsKeys.includes(key)) {
          drillDown.childValue = key;
          break;
        }
      }
      drillDown.children = this.drillDownOption.map(item => ({
        ...item,
        needTips: true,
      }));
    }
  }

  @Watch('showMenu')
  handleShowMenuChange(val) {
    if (!val) {
      (this.$refs[this.currShowItemRef] as any)?.hideHandler?.();
    }
  }

  @Emit('select')
  handleMenuClick(item: IMenuItem) {
    return item;
  }

  /**
   * @description: 选择单个指标
   * @param {IExtendMetricData} metric
   * @return {*}
   */
  @Emit('metricSelect')
  handleMetricSelect(metric: IExtendMetricData) {
    return metric;
  }

  /**
   * 选中子菜单
   * @param item 菜单
   * @param val 子菜单值
   */
  @Emit('selectChild')
  handleSelectChild(menu: IMenuItem, child: IMenuChildItem) {
    !!menu.childValue && (menu.childValue = child.id);
    const key = `${menu.id}-popover`;
    (this.$refs[key] as any)?.hideHandler?.();
    return {
      child,
      menu,
    };
  }

  @Emit('childMenuToggle')
  handleChildMenuToggle(val: boolean) {
    return val;
  }

  handleGetItemName(options: IMenuChildItem[], id: string) {
    return options.find(item => item.id === id)?.name;
  }

  /**
   * 展示子菜单
   * @param event
   * @param key
   */
  toggleMenuItem(event, key: string) {
    this.showMenuItem = !this.showMenuItem;
    const popoverRef = this.$refs[`${key}-popover`] as any;
    if (popoverRef) {
      if (this.showMenuItem && popoverRef.showHandler) {
        popoverRef.showHandler();
        this.currShowItemRef = `${key}-popover`;
      } else if (!this.showMenuItem && popoverRef.hideHandler) {
        popoverRef.hideHandler();
      }
    }
    event.stopPropagation();
  }
  render() {
    return (
      <ul class='chart-menu'>
        {this.menuList.map(item => {
          const isHidden = !this.list.includes(item.id) || (item.id === 'drill-down' && !item.children.length);
          if (isHidden) return undefined;
          /**
           * 子菜单
           */
          const childTpl = item => (
            <ul
              class='child-list'
              slot='content'
            >
              {item.children.map(child => (
                <li
                  key={child.id}
                  class={['child-list-item', { active: child.id === item.childValue }]}
                  v-bk-tooltips={{
                    content: child.id,
                    placement: 'right',
                    boundary: document.body,
                    disabled: !child.needTips,
                    allowHTML: false,
                  }}
                  onClick={() => this.handleSelectChild(item, child)}
                >
                  {child.icon && <i class={`child-icon icon-monitor ${`icon-${child.icon}`}`} />}
                  {child.name}
                </li>
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
              <span class='menu-item-name'>{!item.checked ? item.name : item.nextName || item.name}</span>
              {!!item.children?.length && item.hasLink && (
                <bk-popover
                  ref={`${item.id}-popover`}
                  class='menu-item-trigger-popover'
                  tippy-options={{
                    trigger: 'click',
                    appendTo: 'parent',
                    onHide: () => {
                      this.showMenuItem = false;
                      this.currShowItemRef = '';
                      return true;
                    },
                  }}
                  animation='slide-toggle'
                  arrow={false}
                  disabled={item.children.length < 2}
                  distance={12}
                  offset={-1}
                  placement='bottom-start'
                  theme='light cycle-list-wrapper child-list-popover'
                >
                  <div
                    class={['menu-item-trigger', { 'menu-item-show': this.showMenuItem }]}
                    onClick={e => {
                      this.toggleMenuItem(e, item.id);
                    }}
                    onMousedown={e => {
                      e.preventDefault();
                    }}
                  >
                    <span
                      class='menu-item-trigger-content'
                      v-bk-overflow-tips
                    >
                      {this.handleGetItemName(item.children, item.childValue)}
                    </span>
                    <i class='bk-icon icon-angle-down' />
                  </div>
                  {childTpl(item)}
                </bk-popover>
              )}
              {item.hasLink ? <i class='icon-monitor icon-mc-link link-icon' /> : undefined}
              {!item.hasLink && item.children?.length && (
                <i class='icon-monitor icon-arrow-right chart-menu-more-icon' />
              )}
            </li>
          );
          if (item.children?.length && !item.hasLink) {
            return (
              <bk-popover
                ref={`${item.id}-popover`}
                class='chart-menu-item-more'
                animation='slide-toggle'
                arrow={false}
                placement='right-start'
                theme='light cycle-list-wrapper child-list-popover more'
              >
                {menuItemTpl}
                {childTpl(item)}
              </bk-popover>
            );
          }
          return menuItemTpl;
        })}
        {this.showAddMetric &&
          this.metrics
            ?.filter((item, index, arr) => arr.map(m => m.metric_id).indexOf(item.metric_id) === index)
            ?.map((item, index) => (
              <li
                key={index}
                class={`chart-menu-item ${index === 0 ? 'segmentation-item' : ''}`}
                onClick={() => this.handleMetricSelect(item)}
              >
                <i class='icon-monitor icon-icon-mc-add-strategy strategy-icon' />
                <span
                  class='field-name'
                  v-bk-overflow-tips
                >
                  {item.metric_field_name}
                </span>
                <i
                  class='bk-icon icon-info-circle tips-icon'
                  v-bk-tooltips={{ content: createMetricTitleTooltips(item), allowHTML: true }}
                />
              </li>
            ))}
      </ul>
    );
  }
}
