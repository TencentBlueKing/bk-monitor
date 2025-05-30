import { defineComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import TextSegmentation from '../../retrieve-v2/search-result-panel/log-result/text-segmentation';
import RetrieveHelper from '../../retrieve-helper';
import useIntersectionObserver from '@/hooks/use-intersection-observer';
import useLocale from '@/hooks/use-locale';

import './grep-cli-result.scss';

export default defineComponent({
  name: 'CliResult',
  props: {
    searchValue: {
      type: String,
      default: '',
    },
    matchMode: {
      type: Object,
      default: () => ({
        caseSensitive: false,
        regexMode: false,
        wordMatch: false,
      }),
    },

    list: {
      type: Array,
      default: () => [],
    },
    fieldName: {
      type: String,
      default: '',
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['load-more'],
  setup(props, { emit }) {
    const refRootElement = ref<HTMLDivElement>();
    const refLoadMoreElement = ref<HTMLDivElement>();
    const { t } = useLocale();

    useIntersectionObserver(refLoadMoreElement, () => {
      emit('load-more');
    });

    watch(
      () => [props.searchValue, props.matchMode],
      () => {
        RetrieveHelper.highLightKeywords([props.searchValue]);
      },
    );

    onMounted(() => {
      RetrieveHelper.setMarkInstance(() => refRootElement.value);
    });

    onBeforeUnmount(() => {
      RetrieveHelper.destroyMarkInstance();
    });

    const getResultRender = () => {
      if (props.list.length === 0) {
        return (
          <bk-exception
            class='exception-wrap-item exception-part'
            type='search-empty'
            scene='part'
            style={{ minHeight: '300px', paddingTop: '100px' }}
          >
            {t('检索结果为空')}
          </bk-exception>
        );
      }
      return props.list.map((row, index) => (
        <div class='cli-result-line'>
          <span class='cli-result-line-number'>{index + 1}</span>
          <div class='cli-result-line-content-wrapper'>
            <TextSegmentation
              field={{ field_name: props.fieldName, is_analyzed: true }}
              content={row[props.fieldName] ?? ''}
              data={row}
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
          style={{ minHeight: '32px', width: '100%' }}
          v-bkloading={{ isLoading: props.isLoading }}
          ref={refLoadMoreElement}
        ></div>
      </div>
    );
  },
});
