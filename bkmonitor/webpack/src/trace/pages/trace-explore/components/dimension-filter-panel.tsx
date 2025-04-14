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

import { defineComponent, shallowRef, watch, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { useDebounceFn } from '@vueuse/core';
import { $bkPopover, Input, OverflowTitle } from 'bkui-vue';
import { AngleDownLine } from 'bkui-vue/lib/icon';

import EmptyStatus, {
  type EmptyStatusOperationType,
  type EmptyStatusType,
} from '../../../components/empty-status/empty-status';
import { useTraceExploreStore } from '../../../store/modules/explore';
import { convertToTree } from '../utils';
import FieldTypeIcon from './field-type-icon';
import StatisticsList from './statistics-list';

import type { IDimensionFieldTreeItem, ConditionChangeEvent, IDimensionField } from '../typing';

import './dimension-filter-panel.scss';

export default defineComponent({
  name: 'DimensionFilterPanel',
  props: {
    list: { type: Array as PropType<IDimensionField[]>, default: () => [] },
    condition: { type: Array as PropType<any[]>, default: () => [] },
    queryString: { type: String, default: '' },
    listLoading: { type: Boolean, default: false },
  },
  emits: ['conditionChange', 'close', 'showEventSourcePopover'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceExploreStore();
    const emptyStatus = shallowRef<EmptyStatusType>('empty');
    /** 字段列表的count统计 */
    const fieldListCount = shallowRef({});
    /* 搜索关键字 */
    const searchVal = shallowRef('');
    /** 搜索结果列表 */
    const searchResultList = shallowRef<IDimensionField[]>([]);
    /** 转化维度列表为树结构 */
    const dimensionTreeList = shallowRef<IDimensionFieldTreeItem[]>([]);
    const topKCancelFn = null;

    watch([() => store.refreshImmediate, () => props.condition, () => props.queryString], () => {
      getFieldCount();
    });

    watch(
      () => props.list,
      list => {
        searchVal.value = '';
        searchResultList.value = list;
        dimensionTreeList.value = convertToTree(searchResultList.value);
        getFieldCount();
      }
    );

    async function getFieldCount() {
      const fields = props.list.reduce((pre, cur) => {
        if (cur.is_option_enabled) pre.push(cur.name);
        return pre;
      }, []);
      if (!fields.length) return;
      const list = await getFieldTopKList({
        limit: 0,
        fields,
      });
      fieldListCount.value = list.reduce((pre, cur) => {
        pre[cur.field] = cur.distinct_count;
        return pre;
      }, {});
    }

    function getFieldTopKList(params) {
      topKCancelFn?.();
      // return getEventTopK(
      //   {
      //     ...props.commonParams,
      //     ...params,
      //   },
      //   {
      //     cancelToken: new CancelToken(c => (topKCancelFn = c)),
      //   }
      // ).catch(() => []);
      console.log(params);

      return Promise.resolve([
        {
          field: 'event_name',
          distinct_count: 25,
          list: [],
        },
        {
          field: 'type',
          distinct_count: 2,
          list: [],
        },
      ]);
    }

    /** 关键字搜索 */
    const handleSearch = useDebounceFn((keyword: string) => {
      searchVal.value = keyword;
      if (!searchVal.value) {
        searchResultList.value = props.list;
        emptyStatus.value = 'empty';
      } else {
        emptyStatus.value = 'search-empty';
        searchResultList.value = props.list.filter(item => item.alias.includes(searchVal.value));
      }
      dimensionTreeList.value = convertToTree(searchResultList.value);
    }, 100);

    function renderDimensionItem(item: IDimensionFieldTreeItem, level = 0) {
      const disabled = !item.children && (!item.is_option_enabled || !fieldListCount.value[item.name]);
      return (
        <div
          key={item.alias}
          style={{ '--level': level }}
          v-bk-tooltips={{
            content: t(item.is_option_enabled ? '该维度暂无数据，无法进行统计分析' : '该字段类型，暂时不支持统计分析'),
            disabled: !disabled,
            interactive: false,
            placement: 'right',
          }}
        >
          <div
            class={{
              'dimension-item': true,
              active: activeFieldName.value === item.name,
              disabled,
              'leaf-item': !item.children,
            }}
            onClick={e => handleDimensionItemClick(e, item)}
          >
            <FieldTypeIcon type={item.type} />
            <OverflowTitle
              class='dimension-name'
              type='tips'
            >
              {item.levelName}
            </OverflowTitle>
            {item.children && [
              <span
                key='object-count'
                class='object-count'
              >
                {item.count}
              </span>,
              <span
                key='object-arrow'
                class='object-arrow'
              >
                <AngleDownLine />
              </span>,
            ]}
            {item.is_option_enabled &&
              !item.children && [
                <span
                  key={`${item.name}__count`}
                  class='dimension-count'
                >
                  {fieldListCount.value[item.name] || 0}
                </span>,
                !item.children && (
                  <i
                    key={`${item.name}__statistics`}
                    class='icon-monitor icon-Chart statistics-icon'
                  />
                ),
              ]}
          </div>

          {item.children && item.expand && (
            <div class='leaf-content'>{item.children.map(child => renderDimensionItem(child, level + 1))}</div>
          )}
        </div>
      );
    }

    /** 已选择的字段 */
    const selectField = shallowRef<IDimensionField>(null);
    const activeFieldName = shallowRef('');
    /** popover实例 */
    const popoverInstance = shallowRef(null);
    const statisticsListRef = shallowRef(null);
    /** 点击维度项后展示统计弹窗 */
    async function handleDimensionItemClick(e: Event, item: IDimensionFieldTreeItem) {
      destroyPopover();
      activeFieldName.value = item.name;
      if (item?.children) {
        item.expand = !item.expand;
      } else {
        if (!item.is_option_enabled || !fieldListCount.value[item.name]) return;
        selectField.value = item;
        popoverInstance.value = $bkPopover({
          target: e.currentTarget as HTMLDivElement,
          content: statisticsListRef.value.$refs.dimensionPopover,
          trigger: 'click',
          placement: 'right',
          theme: 'light',
          arrow: true,
          boundary: 'viewport',
          extCls: 'statistics-dimension-popover-cls',
          width: 400,
          distance: -5,
          onHide() {
            activeFieldName.value = '';
          },
        });
        setTimeout(() => {
          popoverInstance.value.show();
        }, 100);
      }
    }

    function destroyPopover() {
      activeFieldName.value = '';
      popoverInstance.value?.hide(0);
      popoverInstance.value?.uninstall();
      popoverInstance.value = null;
    }

    function handleConditionChange(value: ConditionChangeEvent) {
      emit('conditionChange', value);
    }

    function handleClose() {
      emit('close');
    }

    function renderSkeleton() {
      return (
        <div class='dimension-filter-panel-skeleton'>
          <div class='skeleton-element title' />
          <div class='skeleton-element search-input' />
          {new Array(10).fill(null).map((item, index) => (
            <div
              key={index}
              class='skeleton-element list-item'
            />
          ))}
        </div>
      );
    }

    function emptyOperation(type: EmptyStatusOperationType) {
      if (type === 'clear-filter') {
        searchVal.value = '';
        handleSearch('');
      }
    }

    return {
      t,
      activeFieldName,
      emptyStatus,
      fieldListCount,
      searchVal,
      dimensionTreeList,
      selectField,
      handleSearch,
      renderDimensionItem,
      popoverInstance,
      statisticsListRef,
      handleDimensionItemClick,
      destroyPopover,
      handleConditionChange,
      handleClose,
      renderSkeleton,
      emptyOperation,
    };
  },
  render() {
    if (this.listLoading) return this.renderSkeleton();

    return (
      <div class='dimension-filter-panel-comp'>
        <div class='header'>
          <div class='title'>{this.t('维度过滤')}</div>
          <i
            class='icon-monitor icon-gongneng-shouqi'
            v-bk-tooltips={{ content: this.t('收起') }}
            onClick={this.handleClose}
          />
        </div>
        <div class='search-input'>
          <Input
            v-model={this.searchVal}
            native-attributes={{
              spellcheck: false,
            }}
            placeholder={this.t('搜索 维度字段')}
            type='search'
            clearable
            show-clear-only-hover
            onEnter={this.handleSearch}
            onInput={this.handleSearch}
          />
        </div>

        {this.dimensionTreeList.length ? (
          <div class='dimension-list'>{this.dimensionTreeList.map(item => this.renderDimensionItem(item, 0))}</div>
        ) : (
          <EmptyStatus
            type={this.emptyStatus}
            onOperation={this.emptyOperation}
          />
        )}

        <StatisticsList
          ref='statisticsListRef'
          fieldType={this.selectField?.type}
          isDimensions={this.selectField?.is_dimensions}
          selectField={this.selectField?.name}
          onConditionChange={this.handleConditionChange}
          onShowMore={this.destroyPopover}
        />
      </div>
    );
  },
});
