import { defineComponent } from 'vue';
import './index-set-list.scss';

import * as authorityMap from '../../../../common/authority-map';

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

    /**
     * 多选：选中操作
     * @param item
     * @param value
     */
    const handleIndexSetItemCheck = (item, value) => {
      const targetValue = [];

      // 如果是选中
      if (value) {
        props.value.forEach((v: any) => {
          targetValue.push(v);
        });
        targetValue.push(item.index_set_id);
        emit('value-change', targetValue);
        return;
      }

      // 如果是取消选中
      props.value.forEach((v: any) => {
        if (v !== item.index_set_id) {
          targetValue.push(v);
        }
      });

      emit('value-change', targetValue);
    };

    const getCheckBoxRender = item => {
      if (props.type === 'single') {
        return null;
      }

      return (
        <bk-checkbox
          class='check-box'
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
                class={['index-set-item', { 'no-authority': item.permission?.[authorityMap.SEARCH_LOG_AUTH] }]}
                onClick={e => handleIndexSetItemClick(e, item)}
              >
                <div dir={props.textDir}>
                  <span
                    class={['favorite-icon bklog-icon bklog-lc-star-shape', { 'is-favorite': item.is_favorite }]}
                    onClick={e => handleFavoriteClick(e, item)}
                  ></span>
                  <span class='group-icon'></span>
                  {getCheckBoxRender(item)}
                  <bdi
                    class={['index-set-name', { 'no-data': item.tags?.some(tag => noDataReg.test(tag.name)) ?? false }]}
                  >
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
