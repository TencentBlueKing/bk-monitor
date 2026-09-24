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
import { defineComponent } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { usePopover } from '../../../alarm-center/components/alarm-table/hooks/use-popover';
import ChartCollapse from '../../../trace-explore/components/explore-chart/chart-collapse';

import './resource-collapse-list.scss';

/**
 * @description 资源折叠列表面板
 * 智能体 / Skill / 知识库等资源配置面板结构一致，仅标题、提示与卡片渲染不同，
 * 差异部分通过 props 与插槽（actions / item）承接。
 */
export default defineComponent({
  name: 'ResourceCollapseList',
  props: {
    /** 面板标题 */
    title: {
      type: String,
      required: true,
    },
    /** 标题旁提示内容，为空则不展示提示图标 */
    headerTip: {
      type: String,
      default: '',
    },
    /** 资源数量（用于标题展示） */
    count: {
      type: Number,
      default: 0,
    },
    /** 是否显示刷新按钮 */
    showRefreshBtn: {
      type: Boolean,
      default: true,
    },
    /** 空状态提示文案，为空则使用默认模板 */
    emptyText: {
      type: String,
      default: '',
    },
  },
  emits: {
    /** 清空列表 */
    clear: () => true,
    /** 添加资源 */
    add: () => true,
    /** 刷新资源 */
    refresh: () => true,
  },
  setup(props, { slots, emit }) {
    const { t } = useI18n();
    /** 标题旁提示 popover */
    const tipPopoverTools = usePopover({
      tippyOptions: {
        placement: 'top',
        theme: 'alarm-center-popover max-width-50vw text-wrap',
      },
    });

    /**
     * @description 渲染空状态
     * 优先使用插槽自定义；未提供插槽时使用默认文案 + 添加按钮。
     * @returns {JSX.Element} 空状态 DOM 节点
     */
    const renderEmpty = () => {
      if (slots.empty) {
        return slots.empty();
      }
      return (
        <div class='resource-empty-state'>
          <i class='icon-monitor icon-hint' />
          <span>{props.emptyText || t('暂无数据')}，</span>
          <Button
            theme='primary'
            text
            onClick={() => emit('add')}
          >
            {t('立即添加')}
          </Button>
        </div>
      );
    };

    /**
     * @description 渲染折叠面板头部触发区
     * 包含展开/折叠图标、标题、资源数量及提示图标。
     * @returns {JSX.Element} 头部触发区 DOM 节点
     */
    const renderHeaderTrigger = () => {
      return (
        <div class='header-trigger-wrapper'>
          <i class='icon-monitor icon-mc-triangle-down' />
          <span class='header-trigger-title'>
            {props.title}（{props.count}）
          </span>
          {props.headerTip && (
            <i
              class='icon-monitor icon-hint'
              onMouseenter={e => tipPopoverTools.showPopover(e, props.headerTip)}
              onMouseleave={() => tipPopoverTools.clearPopoverTimer()}
            />
          )}
        </div>
      );
    };

    /**
     * @description 渲染折叠面板头部操作区
     * 包含刷新、清空、添加按钮，刷新按钮可通过 showRefreshBtn 控制。
     * @returns {JSX.Element} 头部操作区 DOM 节点
     */
    const renderHeaderCustom = () => {
      return (
        <div class='header-untrigger-wrapper'>
          {props.showRefreshBtn && (
            <Button
              theme='primary'
              text
              onClick={() => emit('refresh')}
            >
              <i class='icon-monitor icon-zhongzhi1' />
              {t('刷新状态')}
            </Button>
          )}
          <Button
            theme='primary'
            text
            onClick={() => emit('clear')}
          >
            <i class='icon-monitor icon-mc-delete-line' />
            {t('清空')}
          </Button>
          <Button
            theme='primary'
            text
            onClick={() => emit('add')}
          >
            <i class='icon-monitor icon-mc-add' />
            {t('添加')}
          </Button>
        </div>
      );
    };

    return { renderEmpty, renderHeaderTrigger, renderHeaderCustom };
  },
  render() {
    return (
      <ChartCollapse
        class='resource-collapse'
        defaultHeight={0}
        defaultIsExpand={true}
        hasResize={false}
      >
        {{
          headerTrigger: this.renderHeaderTrigger,
          headerCustom: this.renderHeaderCustom,
          default: () => <div class='resource-list'>{!this.count ? this.renderEmpty() : this.$slots.default?.()}</div>,
        }}
      </ChartCollapse>
    );
  },
});
