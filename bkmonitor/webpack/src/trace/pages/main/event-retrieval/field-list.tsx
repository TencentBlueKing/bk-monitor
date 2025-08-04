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

import { Collapse, Progress } from 'bkui-vue';
import { EnlargeLine, NarrowLine } from 'bkui-vue/lib/icon';
import { deepClone } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { SPAN_KIND_MAPS, SPAN_STATUS_CODE } from '../../../store/constant';

import type { FieldListType, FieldValue } from 'monitor-pc/pages/data-retrieval/typings';

import './field-list.scss';

export interface IDimissionItem {
  alias?: string;
  id: string;
  percent: number;
}

export type TraceFieldValue = {
  list_key: string; // 列表取值索引
} & FieldValue;

type AliasMapType = {
  [key: string]: string;
};

/** 维度值记录排名前5 */
const TOP_NUM = 5;

const IProps = {
  value: {
    type: Array as PropType<TraceFieldValue[]>,
    default: () => [],
  },
  total: {
    // 记录总数
    type: Number,
    default: 0,
  },
  allowDisplay: {
    // 允许控制显示隐藏
    type: Boolean,
    default: false,
  },
};

export default defineComponent({
  props: IProps,
  emits: ['addCondition', 'showMoreChange', 'checkedChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 展开字段的key 默认展开 */
    const expandedData = ref(['rootService']);
    const localValue = ref<TraceFieldValue[]>([]);
    localValue.value = deepClone(props.value);

    watch(
      () => props.value,
      v => {
        localValue.value = v;
      }
    );

    /**
     * @description: 切换字段的显示、隐藏
     * @param {Event} evt 点击事件
     * @param {TraceFieldValue} item 单条字段数据
     * @return {*}
     */
    const handleFieldChecked = (evt: Event, item: TraceFieldValue, index: number) => {
      evt.stopPropagation();
      emit('checkedChange', {
        index,
        checked: !item.checked,
        field: item.field,
      });
    };

    /**
     * @description: 添加为过滤条件
     * @param {FieldListType.AddConditionType} method 添加条件的method
     * @return {IFilterCondition.localValue}
     */
    const handleAddConditon = (method: FieldListType.AddConditionType, item: TraceFieldValue, val: IDimissionItem) => {
      emit('addCondition', {
        key: item.field,
        method,
        value: [val.id],
        condition: 'and',
      });
    };

    /**
     * @description: 处理维度别名
     */
    const handleAlias = (key: string) => {
      const aliasMap: AliasMapType = {
        event_name: '事件名',
        target: '目标',
        root_service_status_code: t('状态码'),
        root_service: t('入口服务'),
        root_span_name: t('入口接口'),
        root_service_category: t('调用类型'),
        'service.name': t('所属服务'),
        span_name: t('Span 名称'),
        status: t('状态码'),
        kind: t('调用类型'),
        interface_type: t('接口类型'),
        interface_name: t('接口名'),
        interface_service_name: t('所属Service'),
        service_name_in_service_statistic: 'Service',
        service_type_in_service_statistic: t('服务类型'),
      };
      return aliasMap[key] || key;
    };

    const handleChangeShowMore = (key: string) => {
      emit('showMoreChange', key);
    };

    const { total, allowDisplay } = toRefs(props);

    return {
      expandedData,
      handleFieldChecked,
      handleAddConditon,
      handleAlias,
      total,
      allowDisplay,
      localValue,
      handleChangeShowMore,
      t,
    };
  },
  render() {
    const titleSlot = (item: TraceFieldValue, index: number) => (
      <div class={['collapse-item-title', { 'is-expanded': this.expandedData.includes(item.key) }]}>
        <span class='title-left'>
          <i class={['icon-monitor', 'icon-mc-triangle-down']} />
          {/* <span class="type-icon">#</span> */}
          <span class='field-name'>{item.fieldName}</span>
          <span class='field-value-count'>{item.total}</span>
        </span>
        <span class='title-center' />
        {this.allowDisplay ? (
          <span
            class='display-btn'
            onClick={evt => this.handleFieldChecked(evt, item, index)}
          >
            {item.checked ? this.t('隐藏') : this.t('展示')}
          </span>
        ) : undefined}
      </div>
    );

    const contentSlot = (item: TraceFieldValue) => (
      // 统计排名前五的数量
      // const count = item.dimensions.reduce((total, cur, index) => {
      //   if (index < TOP_NUM) {
      //     return total + cur.count;
      //   }
      //   return total;
      // }, 0);
      <div class={['field-list-item-content']}>
        {/* <div class="field-list-item-desc">{this.t('{0}/{1}条记录中数量排名前
          {2} 的数', [count, this.total, TOP_NUM])}</div> */}
        {item.dimensions.map((val: IDimissionItem, i) => {
          if (!item.showMore && i + 1 > TOP_NUM) return undefined;
          return (
            <div
              key={val.id || i}
              class='val-percent-item'
            >
              <div class='val-percent-progress'>
                <div class='val-percent-text'>
                  {
                    // 调用类型 这一类需要转换文本，但又不能影响查询语句的自动填写。
                    (() => {
                      if (['kind', 'status.code'].includes(item.field)) {
                        const maps = item.field === 'kind' ? SPAN_KIND_MAPS : SPAN_STATUS_CODE;
                        const id = maps[val.id];
                        return (
                          <span
                            class='field'
                            title={id}
                          >
                            {id || '--'}
                          </span>
                        );
                      }
                      return (
                        <span
                          class='field'
                          title={val.id}
                        >
                          {/* 调用类型比较特殊，不能直接显示值，要显示他的别名。 */}
                          {val.alias || val.id || '--'}
                        </span>
                      );
                    })()
                  }
                  <span class='percent'>{val.percent}%</span>
                </div>
                <Progress
                  percent={val.percent}
                  show-text={false}
                  stroke-width={4}
                  theme='success'
                />
              </div>
              <div class='icon-box'>
                <EnlargeLine
                  class='icon'
                  onClick={() => this.handleAddConditon('AND', item, val)}
                />
                <NarrowLine
                  class='icon'
                  onClick={() => this.handleAddConditon('NOT', item, val)}
                />
              </div>
            </div>
          );
        })}
        {item.dimensions.length > 5 && !item.showMore ? (
          <div class='link-btn'>
            <span
              class='btn-more'
              onClick={() => this.handleChangeShowMore(item.key)}
            >
              {this.t('更多')}
            </span>
          </div>
        ) : undefined}
      </div>
    );

    return (
      <Collapse
        class='collapse-wrap collapse-wrap-event'
        v-model={this.expandedData}
        v-slots={{
          default: (item: TraceFieldValue, index: number) => titleSlot(item, index),
          content: (item: TraceFieldValue) => contentSlot(item),
        }}
        idFiled='key'
        list={this.localValue}
      >
        {/* <div class="collapse-wrap collapse-wrap-event">
          {
            this.value.map((item, index) => (
              <Collapse.CollapseItem
                key={item.key}
                class={['collapse-item', { 'is-empty': !item.dimensions?.length }]}
                name={item.key}
                disabled={!item.dimensions?.length}
                scopedSlots={{
                  default: () => titleSlot(item, index),
                  content: () => contentSlot(item)
                }}>
              </Collapse.CollapseItem>
            ))
          }
        </div> */}
      </Collapse>
    );
  },
});
