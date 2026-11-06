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
import { type PropType, computed, defineComponent, nextTick, shallowRef, watch } from 'vue';

import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import ProfilingSkeleton from './profiling-skeleton';
import RetrievalFilter from '@/components/retrieval-filter/retrieval-filter';
import {
  type IFilterField,
  type IGetValueFnParams,
  type IWhereItem,
  type IWhereValueOptionsItem,
  EFieldType,
  EMethod,
  EMode,
} from '@/components/retrieval-filter/typing';
import useUserConfig from '@/hooks/useUserConfig';

export default defineComponent({
  name: 'ProfilingExploreFilter',
  props: {
    fields: { type: Array as PropType<IFilterField[]>, default: () => [] },
    where: { type: Array as PropType<IWhereItem[]>, default: () => [] },
    commonWhere: { type: Array as PropType<IWhereItem[]>, default: () => [] },
    label: { type: String, default: '' },
    configKey: { type: String, required: true },
    getValues: {
      type: Function as PropType<(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>>,
      required: true,
    },
    selectedFavorite: { type: Object, default: null },
    placeholder: { type: String, default: '' },
    loading: Boolean,
  },
  emits: {
    change: (_where: IWhereItem[]) => true,
    commonChange: (_where: IWhereItem[]) => true,
    search: () => true,
    favorite: (_edit: boolean) => true,
  },
  setup(props) {
    const { t } = useI18n();
    const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();
    // 配置读取完成前先展开，常驻区显示骨架；确认没有常驻字段和取值后再收起。
    const showResident = shallowRef(true);
    const residentKeys = shallowRef<string[]>([]);
    let configKey = '';
    let configRequest: null | Promise<string[]> = null;

    // 常驻组件只保留字段列表中存在的字段；没有数据时标签为空，需把已保存的常驻字段补进字段列表。
    const filterFields = computed<IFilterField[]>(() => {
      const names = new Set(props.fields.map(item => item.name));
      const missing = residentKeys.value
        .filter(key => !names.has(key))
        .map(key => ({
          name: key,
          alias: key,
          type: EFieldType.keyword,
          isEnableOptions: true,
          methods: [{ value: EMethod.eq, alias: '=' }],
        }));
      return missing.length ? [...props.fields, ...missing] : props.fields;
    });

    // 常驻组件在读取配置后立即按字段匹配，等补齐字段并完成渲染后再返回，避免已保存字段被过滤。
    function getResidentConfig(key: string) {
      if (key !== configKey || !configRequest) {
        configKey = key;
        configRequest = handleGetUserConfig<string[]>(key)
          .catch(() => undefined)
          .then(async saved => {
            const list = Array.isArray(saved) ? saved.filter(item => typeof item === 'string') : [];
            if (configKey === key) residentKeys.value = list;
            await nextTick();
            return list;
          });
      }
      return configRequest;
    }

    async function setResidentConfig(value: string) {
      const saved = await handleSetUserConfig(value);
      if (saved) {
        const list = JSON.parse(value) as string[];
        residentKeys.value = list;
        configRequest = Promise.resolve(list);
      }
      return saved;
    }

    watch(
      () => props.configKey,
      async (key, _, onCleanup) => {
        let active = true;
        onCleanup(() => {
          active = false;
        });
        residentKeys.value = [];
        if (!key) return;
        showResident.value = true;
        const list = await getResidentConfig(key);
        if (!active) return;
        showResident.value = list.length > 0 || props.commonWhere.some(item => item.value?.length);
      },
      { immediate: true }
    );
    return { t, filterFields, getResidentConfig, setResidentConfig, showResident };
  },
  render() {
    return (
      <div
        class='profiling-filter-row'
        aria-busy={this.loading}
      >
        {this.label && <div class='profiling-filter-label'>{this.label}</div>}
        {this.loading ? (
          <ProfilingSkeleton variant='filter' />
        ) : (
          <RetrievalFilter
            v-slots={{
              default: () => <span class='profiling-ui-mode'>{this.t('UI 模式')}</span>,
              residentSkeleton: () => <ProfilingSkeleton variant='resident' />,
            }}
            commonWhere={this.commonWhere}
            defaultShowResidentBtn={this.showResident}
            fields={this.filterFields}
            filterMode={EMode.ui}
            getValueFn={this.getValues}
            handleGetUserConfig={this.getResidentConfig}
            handleSetUserConfig={this.setResidentConfig}
            placeholder={this.placeholder || this.t('请选择查询条件')}
            residentSettingOnlyId={this.configKey}
            selectFavorite={this.selectedFavorite}
            where={this.where}
            isShowClear
            isShowCopy
            isShowFavorite
            isShowResident
            isSingleMode
            onCommonWhereChange={where => this.$emit('commonChange', where)}
            onCopyWhere={where => copyText(JSON.stringify(where))}
            onFavorite={edit => this.$emit('favorite', edit)}
            onSearch={() => this.$emit('search')}
            onWhereChange={where => this.$emit('change', where)}
          />
        )}
      </div>
    );
  },
});
