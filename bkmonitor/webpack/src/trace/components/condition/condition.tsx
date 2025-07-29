/* eslint-disable vue/multi-word-component-names */
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
import { type PropType, defineComponent, ref, watch } from 'vue';

import { Cascader, Dropdown, Select, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import DurationFilter from '../../pages/main/duration-filter/duration-filter';

import './condition.scss';

interface IConditionList {
  label: string;
  value: string;
}

interface IConditionValueList {
  text: string;
  value: string;
}

export default defineComponent({
  name: 'Condition',
  props: {
    isInclude: {
      type: Boolean,
      default: true,
    },
    labelValue: {
      type: String,
      default: '',
    },
    labelList: {
      type: Array as () => Array<{ label: string; value: string }>,
      default: () => [],
    },
    selectedCondition: {
      type: Object,
      default: () => ({
        label: '',
        value: '',
      }),
    },
    // 用作控制显示哪一种类型的 输入框 。（复选，区间，或特殊框）
    conditionType: {
      type: String,
      default: '',
    },
    conditionList: {
      type: Array as PropType<Array<IConditionList>>,
      default: () => [],
    },
    conditionValueList: {
      type: Array as PropType<Array<IConditionValueList>>,
      default: () => [],
    },
    durationRange: {
      type: Array as PropType<Array<number>>,
      default: () => [],
    },
    selectedConditionValue: {
      type: Array,
      default: () => [],
    },
  },
  emits: [
    'IncludeChange',
    'delete',
    'conditionValueChange',
    'selectComplete',
    'conditionChange',
    'durationRangeChange',
    'itemConditionChange',
    'conditionValueClear',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    const label = ref(t('请选择'));
    const traverseIds = (obj: any, targetID: string) => {
      if (obj.id === targetID) {
        label.value = obj.name;
      }
      if (obj.children) {
        obj.children.forEach(childObj => {
          traverseIds(childObj, targetID);
        });
      }
    };
    watch(
      () => [props.labelList, props.labelValue],
      () => {
        props.labelList.forEach(item => {
          traverseIds(item, props.labelValue);
        });
      },
      { immediate: true }
    );
    const hoverArea = ref([]);

    const cascaderChange = v => {
      emit('itemConditionChange', v);
    };

    const labelHoverStatus = ref(false);
    const setLabelHoverStatus = (v: boolean) => {
      labelHoverStatus.value = v;
    };

    const labelActiveStatus = ref(false);
    const cascaderToggle = (v: boolean) => {
      labelActiveStatus.value = v;
    };

    const conditionTypeActiveStatus = ref(false);

    const renderDom = () => (
      <div>
        {/* 条件名称、条件、删除、是否参与 */}
        <div class='head-row'>
          <div class='cascader'>
            <span
              class={{
                label: true,
                'label-hover': labelHoverStatus.value,
                'label-active': labelActiveStatus.value,
                'label-disabled': !props.isInclude,
              }}
            >
              {label.value}
            </span>
            {props.isInclude && (
              <Cascader
                v-model={hoverArea.value}
                clearable={false}
                list={props.labelList}
                trigger='hover'
                onChange={v => cascaderChange(v)}
                onMouseout={() => setLabelHoverStatus(false)}
                onMouseover={() => setLabelHoverStatus(true)}
                onToggle={v => cascaderToggle(v)}
              />
            )}
            {/* <Select
            popoverMinWidth={240}
            disabled={!props.isInclude}
            onToggle={v => cascaderToggle(v)}
            onChange={v => emit('itemConditionChange', v)}
            v-slots={{
              trigger: <span class='label' class={{
                'label-hover': labelHoverStatus.value,
                'label-active': labelActiveStatus.value,
                'label-disabled': !props.isInclude
              }}
              onMouseover={() => setLabelHoverStatus(true)}
              onMouseout={() => setLabelHoverStatus(false)}
              >{label.value}</span>
            }}>
            {
              props.labelList.map(item => <Select.Option value={item.value} label={item.key} disabled={item.disabled}/>)
            }
          </Select> */}
          </div>
          <Dropdown
            style='flex-shrink: 0;'
            v-slots={{
              content: () => (
                <Dropdown.DropdownMenu>
                  {props.conditionList.map(item => (
                    <Dropdown.DropdownItem onClick={() => emit('conditionChange', item)}>
                      {item.label}
                    </Dropdown.DropdownItem>
                  ))}
                </Dropdown.DropdownMenu>
              ),
            }}
            disabled={!props.isInclude}
            placement='bottom-start'
            trigger='click'
            onHide={() => (conditionTypeActiveStatus.value = false)}
            onShow={() => (conditionTypeActiveStatus.value = true)}
          >
            {/* 这里是 操作符 选择器 */}
            {props.conditionType === 'select' && (
              <span
                class={{
                  'condition-type': true,
                  'condition-type-selected': !!props.selectedCondition.value,
                  'condition-type-active': conditionTypeActiveStatus.value,
                  'condition-type-disabled': !props.isInclude,
                }}
              >
                {props.selectedCondition.label}
              </span>
            )}
          </Dropdown>
          {props.conditionType === 'duration' && (
            <div style='margin-left: 8px;font-size: 12px;color: #9B9DA1;'>
              <span>is between</span>
              <span>{`（${t('支持')} ns, μs, ms, s）`}</span>
            </div>
          )}
          <i
            class='icon-monitor icon-mc-delete-line'
            onClick={() => emit('delete', props.labelValue)}
          />
          <Switcher
            size='small'
            theme='primary'
            value={props.isInclude}
            onChange={() => emit('IncludeChange')}
          />
        </div>

        {/* 复选框 */}
        {props.conditionType === 'select' && (
          <Select
            style='margin-top: 4px;'
            modelValue={props.selectedConditionValue}
            placeholder={t('请选择')}
            filterable
            multiple
            onBlur={() => props.isInclude && emit('selectComplete')}
            onChange={v => emit('conditionValueChange', v)}
            onClear={() => emit('conditionValueClear')}
          >
            {props.conditionValueList.map(item => (
              <Select.Option
                label={item.text}
                value={item.value}
              />
            ))}
          </Select>
        )}

        {/* 区间选择 */}
        {props.conditionType === 'duration' && (
          <DurationFilter
            style='margin-top: 4px;'
            range={props.durationRange ?? undefined}
            onChange={(v: number[]) => emit('durationRangeChange', v)}
          />
        )}

        {/* 特殊：用作条件查询 */}
        {/* TODO：视接口是否完成再加这个 条件查询 */}
      </div>
    );

    return {
      renderDom,
    };
  },
  render() {
    return this.renderDom();
  },
});
