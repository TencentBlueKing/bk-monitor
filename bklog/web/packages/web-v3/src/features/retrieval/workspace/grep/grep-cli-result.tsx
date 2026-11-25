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
import { computed, defineComponent, PropType, ref } from 'vue';

import { Button as TButton } from 'tdesign-vue-next';
import EmptyStatus from '@/shared/ui/empty-status/index.vue';
import { ListLoadingSkeleton } from '@/shared/ui/loading/list-skeleton';
import useIntersectionObserver from '@/shared/composables/use-intersection-observer';
import useLocale from '@/shared/composables/use-locale';

import RetrieveHelper from '../../retrieve-helper';
import ScrollTop from '../../workbench/components/scroll-top/index';
import TextSegmentation from '../../workbench/components/text-segmentation/index';
import useTextAction from '../../workbench/hooks/use-text-action';
import type { GrepRequestResult } from './types';

import './grep-cli-result.scss';

export default defineComponent({
  name: 'CliResult',
  props: {
    grepRequestResult: {
      type: Object as PropType<GrepRequestResult>,
      default: (): GrepRequestResult => ({
        offset: 0,
        is_loading: false,
        list: [],
        has_more: false,
        is_error: false,
        exception_msg: '',
      }),
    },
    fieldName: {
      type: String,
      default: '',
    },
  },
  emits: ['load-more', 'params-change', 'retry', "loadMore", "paramsChange"],
  setup(props, { emit }) {
    const refRootElement = ref<HTMLDivElement>();
    const refLoadMoreElement = ref<HTMLDivElement>();
    const { t } = useLocale();
    const { handleOperation } = useTextAction(emit, 'grep');

    const isLoadingValue = computed(() => props.grepRequestResult.is_loading);

    useIntersectionObserver(
      () => refLoadMoreElement.value,
      (entry: IntersectionObserverEntry) => {
        if (entry.isIntersecting && props.grepRequestResult?.list?.length && props.grepRequestResult?.has_more
          && !props.grepRequestResult.is_error && !props.grepRequestResult.is_loading) {
          emit('load-more');
        }
      },
      {
        root: document.querySelector(RetrieveHelper.globalScrollSelector),
      },
    );

    const handleMenuClick = (event: { option: any; isLink: any; }) => {
      const { option, isLink } = event;
      const isParamsChange = handleOperation(option.operation, {
        value: option.value,
        fieldName: option.fieldName,
        operation: option.operation,
        isLink,
        depth: option.depth,
        displayFieldNames: option.displayFieldNames,
      });

      emit('params-change', { isParamsChange, option });
    };

    const getResultRender = () => {
      const { is_loading: isLoading, is_error: isError, list, exception_msg: errorMessage } = props.grepRequestResult;
      if (isLoading && list.length === 0) {
        return (
          <div class='grep-cli-result-skeleton'>
            <ListLoadingSkeleton variant='log-table' />
          </div>
        );
      }

      if (list.length === 0 || !props.fieldName) {
        return (
          <div class='bklog-table-empty-region grep-cli-result-empty'>
            <EmptyStatus
              emptyType={props.fieldName && isError ? '500' : 'search-empty'}
              description={!props.fieldName ? t('请选择字段') : isError ? errorMessage || undefined : t('检索结果为空')}
              showOperation={Boolean(props.fieldName && isError)}
              onOperation={() => emit('retry')}
            />
          </div>
        );
      }

      return props.grepRequestResult.list.map((row, index) => (
        <div
          key={index}
          class='cli-result-line'
        >
          <span class='cli-result-line-number'>{index + 1}</span>
          <div class='cli-result-line-content-wrapper'>
            <TextSegmentation
              content={row[props.fieldName] ?? ''}
              data={row}
              field={{ field_name: props.fieldName, is_analyzed: true }}
              onMenu-click={handleMenuClick}
            />
          </div>
        </div>
      ));
    };

    return () => (
      <div
        id={RetrieveHelper.logRowsContainerId}
        ref={refRootElement}
        class='cli-result-container'
      >
        {getResultRender()}
        <div
          id='load_more_element'
          ref={refLoadMoreElement}
          style={{ minHeight: '32px', width: '100%', justifyContent: 'center' }}
          class='cli-result-line'
        >
          {isLoadingValue.value && props.grepRequestResult.list.length > 0 && (
            <div style={{ minHeight: '64px', fontSize: '12px', padding: '20px' }}><span class='bklog-loading-mark' role='status' aria-label='Loading' /></div>
          )}
          {!isLoadingValue.value && props.grepRequestResult.is_error && props.grepRequestResult.list.length > 0 && (
            <TButton variant='text' theme='primary' onClick={() => emit('retry')}>
              {t('重试')}
            </TButton>
          )}
        </div>
        <ScrollTop></ScrollTop>
      </div>
    );
  },
});
