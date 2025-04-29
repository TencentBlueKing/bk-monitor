import { defineComponent } from 'vue';
import './index-set-list.scss';

import * as authorityMap from '../../../../common/authority-map';
import useChoice from './use-choice';

export default defineComponent({
  props: {
    list: {
      type: Array,
      default: () => [],
    },
    type: {
      type: String,
      default: 'single',
    },
    value: {
      type: Array,
      default: () => [],
    },
    textDir: {
      type: String,
      default: 'ltr',
    },
  },
  emits: ['value-change'],
  setup(props, { emit }) {
    const handleIndexSetTagItemClick = (item: any, tag: any) => {
      console.log(item, tag);
    };

    /**
     * 索引集选中操作
     * @param e
     * @param item
     */
    const handleIndexSetItemClick = (e: MouseEvent, item: any) => {
      if (props.type === 'single') {
        emit('value-change', [item.index_set_id]);
      }
    };

    const handleFavoriteClick = (e: MouseEvent, item: any) => {};

    const { handleIndexSetItemCheck } = useChoice(props, { emit });

    const getCheckBoxRender = item => {
      if (props.type === 'single') {
        return null;
      }

      return (
        <bk-checkbox
          style='margin-right: 4px'
          checked={props.value.includes(item.index_set_id)}
          on-change={value => handleIndexSetItemCheck(item, value)}
        ></bk-checkbox>
      );
    };

    const noDataReg = /^No\sData$/i;

    return () => {
      return (
        <div class='bklog-v3-index-set-list'>
          {props.list.map((item: any) => {
            return (
              <div
                class={[
                  'index-set-item',
                  {
                    'no-authority': item.permission?.[authorityMap.SEARCH_LOG_AUTH],
                    active: props.value.includes(item.index_set_id),
                  },
                ]}
                onClick={e => handleIndexSetItemClick(e, item)}
              >
                <div dir={props.textDir}>
                  <span
                    class={['favorite-icon bklog-icon bklog-lc-star-shape', { 'is-favorite': item.is_favorite }]}
                    onClick={e => handleFavoriteClick(e, item)}
                  ></span>
                  <span class='group-icon'></span>

                  <bdi
                    class={['index-set-name', { 'no-data': item.tags?.some(tag => noDataReg.test(tag.name)) ?? false }]}
                  >
                    {getCheckBoxRender(item)}
                    {item.index_set_name}
                  </bdi>
                </div>
                <div class='index-set-tags'>
                  {item.tags.map((tag: any) => (
                    <span
                      class='index-set-tag-item'
                      onClick={() => handleIndexSetTagItemClick(item, tag)}
                    >
                      {tag.name}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      );
    };
  },
});
