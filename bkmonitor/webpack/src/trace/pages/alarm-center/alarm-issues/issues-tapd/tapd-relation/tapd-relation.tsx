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

import { type PropType, defineComponent, shallowRef, toRef, watch } from 'vue';

import { Select } from 'bkui-vue';
import { debounce } from 'lodash';
import OverflowTips from 'trace/directive/overflow-tips';
import { useI18n } from 'vue-i18n';

import { useTapdSelect } from '../composables/use-tapd-select';
import { TapdStatusMap } from '../typing';

import './tapd-relation.scss';

export default defineComponent({
  name: 'TapdRelation',
  directive: {
    OverflowTips,
  },
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
    changeTapdItems: (_val: { tapd_id: string; tapd_title: string; tapd_type: string }[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const errMsg = shallowRef('');

    const bizIdRef = toRef(props, 'bizId');
    const workspaceIdRef = toRef(props, 'workspaceId');
    const tapdTypeRef = toRef(props, 'tapdType');

    const { list, loading, scrollLoading, tapdMaps, isToggle, fetchData, handleSearch, handleScrollEnd } =
      useTapdSelect({
        bizId: bizIdRef,
        workspaceId: workspaceIdRef,
        tapdType: tapdTypeRef,
      });

    /** 搜索输入防抖处理（300ms），避免频繁触发接口请求 */
    const handleSearchDebounce = debounce(handleSearch, 300);

    /** 当查询参数变化时重新加载列表 */
    watch(
      () => [props.workspaceId, props.tapdType],
      () => {
        if (props.workspaceId && props.tapdType) {
          fetchData();
        }
      }
    );

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
      emit(
        'changeTapdItems',
        val
          .map(id => {
            const item = tapdMaps.get(id);
            if (item) {
              return {
                tapd_id: id,
                tapd_type: item.tapd_type,
                tapd_title: item.name,
              };
            }
            return null;
          })
          .filter(item => !!item)
      );
    };

    /**
     * Select 下拉面板展开/收起回调
     * - 展开时：清空错误提示并触发首加载数据
     * - 收起时：执行校验（用于提交前的表单验证）
     */
    const handleToggle = (val: boolean) => {
      isToggle.value = val;
      if (val) {
        errMsg.value = '';
        // 每次展开都重新拉取最新数据，保证数据一致性
        fetchData();
      } else {
        validate();
      }
    };

    return {
      errMsg,
      t,
      list,
      loading,
      scrollLoading,
      handleSearchDebounce,
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
                loading={this.loading}
                modelValue={this.modelValue}
                multiple={true}
                noDataText={this.loading ? this.t('加载中...') : this.t('无数据')}
                scrollLoading={this.scrollLoading}
                filterable
                onScroll-end={this.handleScrollEnd}
                onSearch-change={this.handleSearchDebounce}
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
                      <span class='tapd-id'>#TAPD-{item.id}</span>
                      <span
                        class='tapd-title'
                        v-overflow-tips
                      >
                        {item.name}
                      </span>
                      <span
                        style={{
                          borderColor: TapdStatusMap?.[item.status]?.color || '#7C8597',
                          color: TapdStatusMap?.[item.status]?.color || '#7C8597',
                        }}
                        class='tapd-status'
                      >
                        {item?.status_display_name || TapdStatusMap?.[item.status]?.text || '--'}
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
