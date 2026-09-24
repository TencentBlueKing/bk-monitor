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
import { type PropType, defineComponent } from 'vue';

import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import ProfilingSkeleton from './profiling-skeleton';
import RetrievalFilter from '@/components/retrieval-filter/retrieval-filter';
import {
  type IFilterField,
  type IGetValueFnParams,
  type IWhereItem,
  type IWhereValueOptionsItem,
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
    loading: Boolean,
  },
  emits: {
    change: (_where: IWhereItem[]) => true,
    commonChange: (_where: IWhereItem[]) => true,
    search: () => true,
    favorite: (_edit: boolean) => true,
  },
  setup() {
    const { t } = useI18n();
    const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();
    return { t, handleGetUserConfig, handleSetUserConfig };
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
            commonWhere={this.commonWhere}
            fields={this.fields}
            filterMode={EMode.ui}
            getValueFn={this.getValues}
            handleGetUserConfig={this.handleGetUserConfig}
            handleSetUserConfig={this.handleSetUserConfig}
            placeholder={this.t('请选择查询条件')}
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
          >
            <span class='profiling-ui-mode'>{this.t('UI 模式')}</span>
          </RetrievalFilter>
        )}
      </div>
    );
  },
});
