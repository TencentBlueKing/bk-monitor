/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import {
  type PropType,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  toRefs,
  watch,
} from 'vue';

import { debounce, deepClone } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import type { IFavList, IFavoriteItem } from '../../../typings';

import './favorites-list.scss';

interface IState {
  allowScroll: boolean;
  isExpand: boolean;
  localValue: IFavList.favList[];
}

const IProps = {
  value: {
    type: Array as PropType<IFavoriteItem[]>,
    default: () => [],
  },
  checkedValue: {
    type: Object,
    defalut: () => ({}),
  },
};

export default defineComponent({
  name: 'FavoritesList',
  props: IProps,
  emits: ['delete', 'select'],
  setup(props, { emit }) {
    const state = reactive<IState>({
      /** 收藏数据 */
      localValue: [],
      /** 展开更多 */
      isExpand: false,
      /** 允许过多滚动 */
      allowScroll: false,
    });
    const favMain = ref<HTMLDivElement>();
    const scroll = ref<HTMLDivElement>();
    const favoritesList = ref<HTMLDivElement>();
    const favListRef = ref<HTMLDivElement>();
    const resizeObserver = ref<any>(null);
    const { t } = useI18n();

    onMounted(() => {
      favMain.value?.addEventListener('transitionend', handleExpandEnd, false);
      resizeObsever();
      handleOverflowDebounce();
    });

    onBeforeUnmount(() => {
      favMain.value?.removeEventListener('transitionend', handleExpandEnd, false);
      resizeObserver.value.unobserve(favoritesList.value);
    });

    /**
     * @description: 监听动画结束
     * @param {TransitionEvent} evt
     * @return {*}
     */
    const handleExpandEnd = (evt: TransitionEvent) => {
      if (evt.propertyName === 'max-height' && evt.target === favMain.value) {
        /** 动画完成开启滚动 */
        if (state.isExpand) {
          state.allowScroll = true;
        } else {
          scroll.value?.scrollTo(0, 0);
          state.allowScroll = false;
        }
      }
    };
    /**
     * @description: 展开更多
     * @param {*}
     * @return {*}
     */
    const handleExpandMore = (val = !state.isExpand) => {
      state.isExpand = val;
    };
    const handleFavoriteBlur = () => {
      if (state.isExpand) {
        state.isExpand = false;
      }
    };
    const handleSelectFav = (e: Event, item: IFavList.favList) => {
      e.stopPropagation();
      emit('select', item.id);
    };
    const handleDeleteItem = (e: Event, id?: number) => {
      e.stopPropagation();
      emit('delete', id);
    };
    const handleHighlight = (item: IFavList.favList) => {
      const { queryParams } = item.config;
      const isSame =
        JSON.stringify(queryParams.filter_dict) === JSON.stringify(props.checkedValue?.filter_dict || {}) &&
        queryParams.app_name === props.checkedValue?.app_name &&
        queryParams.query_string === props.checkedValue?.query_string;
      return isSame;
    };
    const resizeObsever = () => {
      resizeObserver.value = new ResizeObserver(() => {
        removeOverflow();
        handleOverflow();
      });
      resizeObserver.value.observe(favoritesList.value);
    };
    /**
     * @desc 插入超出提示
     * @param { * } target
     * @param { Number } num
     */
    const insertOverflow = (target: any, num: number) => {
      if (state.isExpand) return;
      const li = document.createElement('li');
      const div = document.createElement('div');
      li.className = 'fav-overflow-item';
      div.className = 'tag';
      div.innerText = `+${num}`;
      li.appendChild(div);
      favListRef.value?.insertBefore(li, target);
    };
    /**
     * @desc 控制超出省略提示
     */
    const handleOverflow = async () => {
      removeOverflow();
      const list = favListRef.value as HTMLDivElement;
      const childs = list.children;
      const overflowTagWidth = 22;
      const listWidth = list.offsetWidth;
      let totalWidth = 0;
      await nextTick();

      for (const i in childs) {
        const item = childs[i] as HTMLDivElement;
        if (!item.className || item.className.indexOf('fav-list-item') === -1) continue;
        totalWidth += item.offsetWidth + 10;
        // 超出省略
        if (totalWidth + overflowTagWidth + 4 > listWidth) {
          const hideNum = state.localValue.length - +i;
          insertOverflow(item, hideNum > 99 ? 99 : hideNum);
          break;
        }
      }
    };
    /**
     * @desc 移除超出提示
     */
    const removeOverflow = () => {
      const overflowList = favListRef.value?.querySelectorAll('.fav-overflow-item') as any;
      if (!overflowList.length) return;
      overflowList.forEach((item: HTMLDivElement) => {
        favListRef.value?.removeChild(item);
      });
    };
    const handleOverflowDebounce = debounce(handleOverflow, 300, false);

    watch(
      () => props.value,
      newVal => {
        state.localValue = deepClone(newVal);
        handleOverflowDebounce();
      },
      { immediate: true }
    );

    return {
      ...toRefs(state),
      favMain,
      scroll,
      handleExpandMore,
      handleFavoriteBlur,
      handleHighlight,
      favoritesList,
      handleSelectFav,
      handleDeleteItem,
      favListRef,
      t,
    };
  },

  render() {
    return (
      <div
        ref='favoritesList'
        class={['favorites-list-wrap', { 'is-expand': this.isExpand }]}
        tabindex={-1}
        onBlur={() => this.handleFavoriteBlur()}
        onClick={() => this.handleExpandMore()}
      >
        <div
          ref='favMain'
          class='fav-main'
        >
          <div class='box-shadow' />
          <span class='fav-label'>{this.t('收藏')}</span>
          <div
            ref='scroll'
            class={['fav-list-wrap', { 'allow-scroll': this.allowScroll && this.isExpand }]}
          >
            <ul
              ref='favListRef'
              class='fav-list'
            >
              {this.localValue.map((item, index) => (
                <li
                  key={index}
                  class={['fav-list-item', { active: this.handleHighlight(item) }]}
                  onClick={e => this.handleSelectFav(e, item)}
                >
                  <span class='fav-name'>{item.name}</span>
                  <i
                    class='icon-monitor icon-mc-close'
                    onClick={e => this.handleDeleteItem(e, item.id)}
                  />
                </li>
              ))}
            </ul>
          </div>
          <span class='arrow-down-wrap'>
            <i class={['icon-monitor', 'icon-arrow-down', { 'is-expand': this.isExpand }]} />
          </span>
        </div>
      </div>
    );
  },
});
