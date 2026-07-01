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
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { type PropType, computed, defineComponent, shallowRef, toRef, watch } from 'vue';

import { Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useTapdSelect } from '../composables/use-tapd-select';
import { TapdStatusMap } from '../typing';

import './tapd-relation.scss';

export default defineComponent({
  name: 'TapdRelation',
  props: {
    modelValue: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 业务 ID */
    bizId: {
      type: [Number, String],
      default: '',
    },
    /** TAPD 工作空间 ID */
    workspaceId: {
      type: [Number, String],
      default: '',
    },
    /** TAPD 单据类型 */
    tapdType: {
      type: String,
      default: 'story',
    },
  },
  emits: {
    'update:modelValue': (_val: string[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const errMsg = shallowRef('');

    const bizIdRef = toRef(props, 'bizId');
    const workspaceIdRef = toRef(props, 'workspaceId');
    const tapdTypeRef = toRef(props, 'tapdType');

    const { list, loading, scrollLoading, fetchData, handleSearch, handleScrollEnd } = useTapdSelect({
      bizId: bizIdRef,
      workspaceId: workspaceIdRef,
      tapdType: tapdTypeRef,
    });

    /** 当查询参数变化时重新加载列表 */
    watch(
      () => [props.workspaceId, props.tapdType],
      () => {
        if (props.workspaceId && props.tapdType) {
          fetchData();
        }
      }
    );

    /** Select 是否处于加载态（首次或滚动加载） */
    const selectLoading = computed(() => loading.value || scrollLoading.value);

    const validate = async () => {
      if (!props.modelValue.length) {
        errMsg.value = t('请选择单据');
      } else {
        errMsg.value = '';
      }
      return !errMsg.value;
    };

    const handleChange = (val: string[]) => {
      emit('update:modelValue', val);
    };

    const handleToggle = (val: boolean) => {
      if (val) {
        errMsg.value = '';
        /** 打开下拉时触发首加载数据 */
        if (!list.value.length) {
          fetchData();
        }
      } else {
        validate();
      }
    };

    return {
      errMsg,
      t,
      list,
      selectLoading,
      scrollLoading,
      handleChange,
      handleSearch,
      handleScrollEnd,
      handleToggle,
      validate,
    };
  },
  render() {
    return (
      <div class='tapd-sideslider-relation-compoent'>
        <span class='form-header mb-24'>
          <span class='form-header-title'>{this.t('选择单据')}</span>
        </span>
        <div class='form-grid'>
          <div class={'form-item'}>
            <div class={['form-item-title', 'required']}>
              <span>{this.t('选择已有单据')}</span>
            </div>
            <div class={['form-item-content', { 'is-error': this.errMsg }]}>
              <Select
                popoverOptions={{
                  extCls: 'tapd-sideslider-relation-compoent-popover',
                }}
                loading={this.selectLoading}
                modelValue={this.modelValue}
                multiple={true}
                scrollLoading={this.scrollLoading}
                filterable
                onScroll-end={this.handleScrollEnd}
                onSearch-change={this.handleSearch}
                onToggle={this.handleToggle}
                onUpdate:modelValue={this.handleChange}
              >
                {this.list.map(item => (
                  <Select.Option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  >
                    <span class='tapd-select-item'>
                      <span class='tapd-id'>#{item.id}</span>
                      <span class='tapd-title'>{item.name}</span>
                      <span
                        style={{
                          borderColor: TapdStatusMap[item.status].color,
                          color: TapdStatusMap[item.status].color,
                        }}
                        class='tapd-status'
                      >
                        {TapdStatusMap[item.status].text}
                      </span>
                    </span>
                  </Select.Option>
                ))}
              </Select>
              {this.errMsg ? <span class='err-msg'>{this.errMsg}</span> : undefined}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
