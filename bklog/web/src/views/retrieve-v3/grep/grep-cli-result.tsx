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
import useIntersectionObserver from '@/hooks/use-intersection-observer';
import useLocale from '@/hooks/use-locale';
import { computed, defineComponent, PropType, ref } from 'vue';

import RetrieveHelper from '../../retrieve-helper';
import ScrollTop from '../../retrieve-v2/components/scroll-top/index';
import TextSegmentation from '../../retrieve-v2/components/text-segmentation/index';
import useTextAction from '../../retrieve-v2/hooks/use-text-action';

import './grep-cli-result.scss';
import { GrepRequestResult } from './types';

export default defineComponent({
  name: 'CliResult',
  emits: ['load-more', 'params-change'],
  props: {
    fieldName: {
      default: '',
      type: String,
    },
    grepRequestResult: {
      default: () => ({}),
      type: Object as PropType<GrepRequestResult>,
    },
  },
  setup(props, { emit }) {
    const refRootElement = ref<HTMLDivElement>();
    const refLoadMoreElement = ref<HTMLDivElement>();
    const { t } = useLocale();
    const { handleOperation } = useTextAction(emit, 'grep');

    const isLoadingValue = computed(() => props.grepRequestResult.is_loading);

    useIntersectionObserver(
      () => refLoadMoreElement.value,
      (entry: IntersectionObserverEntry) => {
        if (
          entry.isIntersecting &&
          props.grepRequestResult?.list?.length &&
          props.grepRequestResult?.has_more
        ) {
          emit('load-more');
        }
      },
      {
        root: document.querySelector(RetrieveHelper.globalScrollSelector),
      }
    );

    const handleMenuClick = (event) => {
      const { isLink, option } = event;
      const isParamsChange = handleOperation(option.operation, {
        depth: option.depth,
        displayFieldNames: option.displayFieldNames,
        fieldName: option.fieldName,
        isLink,
        operation: option.operation,
        value: option.value,
      });

      emit('params-change', { isParamsChange, option });
    };

    const getExceptionMessage = () => {
      if (props.grepRequestResult.is_loading) {
        return t('loading...'); // Loading message
      }

      return props.fieldName
        ? props.grepRequestResult.exception_msg || t('检索结果为空')
        : '请选择字段';
    };

    const getResultRender = () => {
      if (props.grepRequestResult.list.length === 0 || !props.fieldName) {
        return (
          <bk-exception
            class="exception-wrap-item exception-part"
            scene="part"
            style={{ minHeight: '300px', paddingTop: '100px' }}
            type="search-empty"
          >
            <span style="font-size: 12px;">{getExceptionMessage()}</span>
          </bk-exception>
        );
      }

      return props.grepRequestResult.list.map((row, index) => (
        <div class="cli-result-line" key={index}>
          <span class="cli-result-line-number">{index + 1}</span>
          <div class="cli-result-line-content-wrapper">
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
        class="cli-result-container"
        id={RetrieveHelper.logRowsContainerId}
        ref={refRootElement}
      >
        {getResultRender()}
        <div
          class="cli-result-line"
          id="load_more_element"
          ref={refLoadMoreElement}
          style={{ justifyContent: 'center', minHeight: '32px', width: '100%' }}
        >
          {isLoadingValue.value && props.grepRequestResult.list.length > 0 && (
            <div
              style={{ fontSize: '12px', minHeight: '64px', padding: '20px' }}
            >
              loading...
            </div>
          )}
        </div>
        <ScrollTop></ScrollTop>
      </div>
    );
  },
});
