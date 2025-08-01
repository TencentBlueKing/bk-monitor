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
import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';
import VueJsonPretty from 'vue-json-pretty';

import { EMode } from '../../../../../../components/retrieval-filter/typing';
import useFavoriteType from '../../hooks/use-favorite-type';

import type { IFavoriteGroup } from '../../types';

import './render-favorite-query.scss';
import 'vue-json-pretty/lib/styles.css';

interface IWhereItem {
  condition: string;
  key: string;
  method: string;
  value: string[];
  options?: {
    is_wildcard: boolean;
  };
}

export function mergeWhereList(source: IWhereItem[], target: IWhereItem[]) {
  let result: IWhereItem[] = [];
  const sourceMap: Map<string, IWhereItem> = new Map();
  for (const item of source) {
    sourceMap.set(item.key, item);
  }
  const localTarget = [];
  for (const item of target) {
    const sourceItem = sourceMap.get(item.key);
    if (
      !(
        sourceItem &&
        sourceItem.key === item.key &&
        sourceItem.method === item.method &&
        JSON.stringify(sourceItem.value) === JSON.stringify(item.value) &&
        sourceItem?.options?.is_wildcard === item?.options?.is_wildcard
      )
    ) {
      localTarget.push(item);
    }
  }
  result = [...source, ...localTarget];
  return result;
}

export default defineComponent({
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites'][number]>,
    },
  },
  setup(props) {
    const favoriteType = useFavoriteType();
    const { t } = useI18n();

    const renderMetric = () => {
      if (favoriteType.value !== 'metric') {
        return null;
      }
      const config = (props.data as IFavoriteGroup<'metric'>['favorites'][number]).config;
      if (config.promqlData) {
        return (
          <div>
            {config.promqlData.map(item => (
              <div
                key={`${item.alias}_${item.code}`}
                class='promql-box'
              >
                <div class='promql-label'>
                  {t('查询项')}
                  {item.alias}:
                </div>
                <div class='promql-val'>{item.code}</div>
              </div>
            ))}
          </div>
        );
      }
      return (
        <VueJsonPretty
          data={config.localValue}
          deep={5}
        />
      );
    };

    const renderEvent = () => {
      if (favoriteType.value !== 'event') {
        return null;
      }
      const queryConfig = (props.data as IFavoriteGroup<'event'>['favorites'][number]).config.queryConfig;
      if (queryConfig.query_string) {
        return <span>{queryConfig.query_string}</span>;
      }
      if (queryConfig.where?.length) {
        return (
          <VueJsonPretty
            data={{
              data_source_label: queryConfig.data_source_label || '',
              data_type_label: queryConfig.data_type_label || '',
              table: queryConfig.result_table_id || '',
              where: mergeWhereList(queryConfig.where, queryConfig?.commonWhere || []),
            }}
            deep={5}
          />
        );
      }
      return '*';
    };

    const renderTrace = () => {
      if (favoriteType.value !== 'trace') {
        return null;
      }
      const queryParams = (props.data?.config?.queryParams ||
        {}) as IFavoriteGroup<'trace'>['favorites'][number]['config']['queryParams'];
      const filterMode = props.data?.config?.componentData?.filterMode || EMode.ui;
      if (filterMode === EMode.queryString || queryParams?.query) {
        return <span>{queryParams.query}</span>;
      }
      if (filterMode === EMode.ui || queryParams?.filters?.length) {
        return (
          <VueJsonPretty
            data={{
              filters: queryParams.filters,
              app_name: queryParams?.app_name || '',
              start_time: queryParams?.start_time || '',
              end_time: queryParams?.end_time || '',
              mode: queryParams?.mode || '',
              sort: queryParams?.sort || [],
            }}
            deep={5}
          />
        );
      }
      return '*';
    };

    return () => (
      <div class='favorite-box-favorite-info-query'>
        {renderEvent()}
        {renderMetric()}
        {renderTrace()}
      </div>
    );
  },
});
