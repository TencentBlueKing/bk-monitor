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

import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { Checkbox, Input, Popover, Select, Tag } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useAppReadonlyInject } from '../../../provider';
import {
  COLUMN_ICON_MAP,
  COLUMN_VALUES,
  COMPARE_TYPE_OPTIONS,
  METHOD_OPTIONS,
  TIME_SHIFT_OPTIONS,
} from '../../constants/aggregation';
import { handleCreateCompares, handleCreateItemId } from '../../utils/host-list';
import { PANEL_INTERVAL_LIST } from '@/pages/main/dashboard-panel/utils';

import type { CompareTargetOption, MetricAggregationState, MetricCompareType } from '../../types/aggregation';

import './metric-toolbar.scss';

export default defineComponent({
  name: 'MetricToolbar',
  props: {
    compareListEnable: {
      type: Array as PropType<MetricCompareType[]>,
      default: () => ['none', 'target', 'time'],
    },
    /** Toolbar 当前状态（受控） */
    value: {
      type: Object as PropType<MetricAggregationState>,
      required: true,
    },
    /** 目标对比 - 主目标（当前选中主机） */
    currentTarget: {
      type: String,
      default: '',
    },
    /** 目标对比 - 可选目标列表 */
    targetList: {
      type: Array as PropType<CompareTargetOption[]>,
      default: () => [],
    },
  },
  emits: {
    change: (_patch: Partial<MetricAggregationState>) => true,
    openSetting: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const readonly = useAppReadonlyInject() ?? false;

    const localTargetValue = shallowRef<string[]>([]);
    const localTimeShiftValue = shallowRef<string[]>([]);

    watch(
      () => props.value.compareTargets,
      val => {
        localTargetValue.value = val.map(item => handleCreateItemId(item, true));
      },
      { immediate: true }
    );

    watch(
      () => props.value.timeShift,
      val => {
        localTimeShiftValue.value = val;
      },
      { immediate: true }
    );

    const handleCompareTypeChange = (val: MetricAggregationState['compareType']) => {
      if (val === 'time' && props.value.timeShift.length === 0) {
        emit('change', { compareType: val, timeShift: ['1h'] });
      } else {
        emit('change', { compareType: val });
      }
    };

    /** 列数切换：1 → 2 → 3 → 1 循环 */
    const columnIcon = computed(() => COLUMN_ICON_MAP[props.value.columns] || COLUMN_ICON_MAP[3]);
    const handleColumnSwitch = (columns: number) => {
      emit('change', { columns });
    };

    /** 渲染一个「label + Select」字段 */
    const renderField = (label: string, slot: () => JSX.Element) => (
      <div class='metric-toolbar__field'>
        <span class='metric-toolbar__field-label'>{t(label)}</span>
        {slot()}
      </div>
    );

    /** 对比方式列表 */
    const compareTypeOptions = computed(() =>
      COMPARE_TYPE_OPTIONS.filter(item => props.compareListEnable.includes(item.id))
    );

    /** 目标对比下拉框选择 */
    const compareTargetToggle = shallowRef(false);
    /** 目标对比下拉框选择是否变更 */
    const compareTargetIsChange = shallowRef(false);
    const handleCompareTargetChange = (val: string[]) => {
      localTargetValue.value = val;
      compareTargetIsChange.value = true;
      if (!compareTargetToggle.value) handleCompareTargetCommit();
    };
    const handleCompareTargetToggle = (show: boolean) => {
      compareTargetToggle.value = show;
      if (show) compareTargetIsChange.value = false;
      if (compareTargetIsChange.value && !show) {
        handleCompareTargetCommit();
      }
    };

    /** 下拉框隐藏时提交目标对比变更 */
    const handleCompareTargetCommit = () => {
      const compareTargets = localTargetValue.value.reduce((total, id) => {
        const item = props.targetList.find(item => item.id === id);
        const value = handleCreateCompares(item);
        total.push({ ...value });
        return total;
      }, []);
      emit('change', { compareTargets });
    };

    /** 对比时间下拉框选择 */
    const compareTimeShiftToggle = shallowRef(false);
    /** 对比时间下拉框选择是否变更 */
    const compareTimeShiftIsChange = shallowRef(false);
    const handleCompareTimeShiftChange = (val: string[]) => {
      localTimeShiftValue.value = val;
      compareTimeShiftIsChange.value = true;
      if (!compareTimeShiftToggle.value) handleCompareTimeShiftCommit();
    };
    const handleCompareTimeShiftToggle = (show: boolean) => {
      compareTimeShiftToggle.value = show;
      // 每次打开下拉框时，重置变更态
      if (show) compareTimeShiftIsChange.value = false;
      /** 下拉框隐藏时并且数据有变更，则提交数据 */
      if (compareTimeShiftIsChange.value && !show) {
        handleCompareTimeShiftCommit();
      }
    };

    /** 下拉框隐藏时提交对比时间变更 */
    const handleCompareTimeShiftCommit = () => {
      emit('change', { timeShift: localTimeShiftValue.value });
    };

    const renderCompareExtra = () => {
      if (props.value.compareType === 'target') {
        return (
          <div class='metric-toolbar__compare-target'>
            {props.currentTarget && <Tag class='metric-toolbar__main-target'>{props.currentTarget}</Tag>}
            <span class='metric-toolbar__vs'>VS</span>
            <Select
              class='metric-toolbar__target-select'
              behavior='simplicity'
              displayKey='name'
              idKey='id'
              list={props.targetList}
              modelValue={localTargetValue.value}
              multipleMode='tag'
              placeholder={t('选择目标')}
              collapseTags
              enableVirtualRender
              filterable
              multiple
              onChange={handleCompareTargetChange}
              onToggle={handleCompareTargetToggle}
            />
          </div>
        );
      }
      if (props.value.compareType === 'time') {
        return (
          <Select
            class='metric-toolbar__time-select'
            behavior='simplicity'
            modelValue={localTimeShiftValue.value}
            multipleMode='tag'
            placeholder={t('选择时间')}
            collapseTags
            multiple
            onChange={handleCompareTimeShiftChange}
            onToggle={handleCompareTimeShiftToggle}
          >
            {TIME_SHIFT_OPTIONS.map(item => (
              <Select.Option
                id={item.id}
                key={item.id}
                name={t(item.name)}
              />
            ))}
          </Select>
        );
      }
      return null;
    };

    return () => (
      <div class='metric-toolbar'>
        <div class='metric-toolbar__left'>
          {renderField('汇聚周期', () => (
            <Select
              class='metric-toolbar__agg-select'
              behavior='simplicity'
              clearable={false}
              modelValue={props.value.interval}
              onChange={(v: string) => emit('change', { interval: v })}
            >
              {PANEL_INTERVAL_LIST.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </Select>
          ))}
          {renderField('汇聚方法', () => (
            <Select
              class='metric-toolbar__agg-select'
              behavior='simplicity'
              clearable={false}
              modelValue={props.value.method}
              onChange={(v: string) => emit('change', { method: v })}
            >
              {METHOD_OPTIONS.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </Select>
          ))}
          {renderField('对比方法', () => (
            <Select
              class='metric-toolbar__agg-select'
              behavior='simplicity'
              clearable={false}
              modelValue={props.value.compareType}
              onChange={handleCompareTypeChange}
            >
              {compareTypeOptions.value.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={t(item.name)}
                />
              ))}
            </Select>
          ))}
          {renderCompareExtra()}
        </div>
        <div class='metric-toolbar__right'>
          <Input
            class='metric-toolbar__search'
            behavior='simplicity'
            modelValue={props.value.keyword}
            placeholder={t('搜索 指标')}
            type='search'
            clearable
            onClear={() => emit('change', { keyword: '' })}
            onInput={(v: string) => emit('change', { keyword: v })}
          />
          <Checkbox
            class='metric-toolbar__checkbox'
            modelValue={props.value.showStatistics}
            onChange={(v: boolean) => emit('change', { showStatistics: v })}
          >
            {t('展示统计值')}
          </Checkbox>
          <Checkbox
            class='metric-toolbar__checkbox'
            modelValue={props.value.highlightPeak}
            onChange={(v: boolean) => emit('change', { highlightPeak: v })}
          >
            {t('高亮峰谷值')}
          </Checkbox>
          <Popover
            placement='bottom'
            theme='light metric-toolbar-column-popover'
            trigger='hover'
          >
            {{
              default: () => (
                <div class='metric-toolbar__column-switch'>
                  <i class={['icon-monitor', columnIcon.value]} />
                  <span class='metric-toolbar__column-text'>{t('{n} 列', { n: props.value.columns })}</span>
                </div>
              ),
              content: () => (
                <div class='metric-toolbar__column-menu'>
                  {COLUMN_VALUES.map(value => (
                    <div
                      key={value}
                      class={['metric-toolbar__column-menu-item', { active: props.value.columns === value }]}
                      onClick={() => handleColumnSwitch(value)}
                    >
                      <i class={['icon-monitor', COLUMN_ICON_MAP[value]]} />
                      <span>{t('{n} 列', { n: value })}</span>
                    </div>
                  ))}
                </div>
              ),
            }}
          </Popover>
          {!readonly && (
            <div
              class='metric-toolbar__setting'
              v-bk-tooltips={{ content: t('视图分组管理'), delay: 300 }}
              onClick={() => emit('openSetting')}
            >
              <i class='icon-monitor icon-shezhi1' />
            </div>
          )}
        </div>
      </div>
    );
  },
});
