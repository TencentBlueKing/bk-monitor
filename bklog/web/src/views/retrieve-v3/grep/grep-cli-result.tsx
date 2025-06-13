import { computed, defineComponent, PropType, ref } from 'vue';
import TextSegmentation from '../../retrieve-v2/components/text-segmentation/index';
import RetrieveHelper from '../../retrieve-helper';
import useIntersectionObserver from '@/hooks/use-intersection-observer';
import useLocale from '@/hooks/use-locale';
import useTextAction from '../../retrieve-v2/hooks/use-text-action';
import ScrollTop from '../../retrieve-v2/components/scroll-top/index';

import './grep-cli-result.scss';
import { GrepRequestResult } from './types';

export default defineComponent({
  name: 'CliResult',
  props: {
    grepRequestResult: {
      type: Object as PropType<GrepRequestResult>,
      default: () => ({}),
    },
    fieldName: {
      type: String,
      default: '',
    },
  },
  emits: ['load-more', 'params-change'],
  setup(props, { emit }) {
    const refRootElement = ref<HTMLDivElement>();
    const refLoadMoreElement = ref<HTMLDivElement>();
    const { t } = useLocale();
    const { handleOperation } = useTextAction(emit, 'grep');

    const isLoadingValue = computed(() => props.grepRequestResult.is_loading);

    useIntersectionObserver(
      () => refLoadMoreElement.value,
      (entry: IntersectionObserverEntry) => {
        if (entry.isIntersecting) {
          emit('load-more');
        }
      },
      {
        root: document.querySelector(RetrieveHelper.globalScrollSelector),
      },
    );

    const handleMenuClick = event => {
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
      if (!props.grepRequestResult.is_loading && (props.grepRequestResult.list.length === 0 || !props.fieldName)) {
        return (
          <bk-exception
            class='exception-wrap-item exception-part'
            type='search-empty'
            scene='part'
            style={{ minHeight: '300px', paddingTop: '100px' }}
          >
            {props.fieldName ? props.grepRequestResult.exception_msg || t('检索结果为空') : '请选择字段'}
          </bk-exception>
        );
      }

      return props.grepRequestResult.list.map((row, index) => (
        <div
          class='cli-result-line'
          key={index}
        >
          <span class='cli-result-line-number'>{index + 1}</span>
          <div class='cli-result-line-content-wrapper'>
            <TextSegmentation
              field={{ field_name: props.fieldName, is_analyzed: true }}
              content={row[props.fieldName] ?? ''}
              data={row}
              onMenu-click={handleMenuClick}
            />
          </div>
        </div>
      ));
    };

    return () => (
      <div
        class='cli-result-container'
        ref={refRootElement}
        id={RetrieveHelper.logRowsContainerId}
      >
        {getResultRender()}
        <div
          class='cli-result-line'
          style={{ minHeight: '32px', width: '100%', justifyContent: 'center' }}
          ref={refLoadMoreElement}
          id='load_more_element'
        >
          {isLoadingValue.value && (
            <div style={{ minHeight: '64px', fontSize: '18px', padding: '20px' }}>loading...</div>
          )}
        </div>
        <ScrollTop></ScrollTop>
      </div>
    );
  },
});
