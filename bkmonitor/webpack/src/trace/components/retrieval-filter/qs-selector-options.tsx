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

import { defineComponent, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue';

import { useDebounceFn, useEventListener } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import loadingImg from '../../static/img/spinner.svg';
import EmptyStatus from '../empty-status/empty-status';
import QsSelectorHelp from './qs-selector-help';
import { getQueryStringMethods, QUERY_STRING_CONDITIONS, queryStringColorMap } from './query-string-utils';
import TextHighlighter from './text-highlighter';
import {
  type IFilterField,
  EQueryStringTokenType,
  QS_SELECTOR_OPTIONS_EMITS,
  QS_SELECTOR_OPTIONS_PROPS,
  qsSelectorOptionsDescMap,
} from './typing';

import './qs-selector-options.scss';

interface IOptions {
  desc?: string;
  id: string;
  name: string;
}

export default defineComponent({
  name: 'QsSelectorOptions',
  props: QS_SELECTOR_OPTIONS_PROPS,
  emits: QS_SELECTOR_OPTIONS_EMITS,
  setup(props, { emit }) {
    const elRef = useTemplateRef<HTMLDivElement>('el');
    const optionsRef = useTemplateRef<HTMLDivElement>('options');

    const localOptions = shallowRef<IOptions[]>([]);
    const favoriteOptions = shallowRef<{ content: string; keyword: string; title: string }[]>([]);
    const cursorIndex = shallowRef(-1);
    const loading = shallowRef(false);
    const pageSize = shallowRef(200);
    const page = shallowRef(1);
    const isEnd = shallowRef(false);
    const scrollLoading = shallowRef(false);

    const getSearchFavoriteOptionsDebounce = useDebounceFn(() => {
      getSearchFavoriteOptions();
    }, 100);
    const handleGetOptionsDebounce = useDebounceFn(() => {
      handleGetOptions();
    }, 500);
    let cleanup = () => {};

    const { t } = useI18n();

    watch(
      () => props.type,
      () => {
        localOptions.value = [];
        handleGetOptionsProxy();
      },
      { immediate: true }
    );
    watch(
      () => props.search,
      () => {
        handleGetOptionsProxy();
      },
      { immediate: true }
    );
    watch(
      () => props.show,
      val => {
        if (val) {
          localOptions.value = [];
          handleGetOptionsProxy();
          cleanup = useEventListener('keydown', handleKeydownEvent);
        } else {
          cleanup?.();
        }
      },
      { immediate: true }
    );
    watch(
      () => props.queryString,
      () => {
        getSearchFavoriteOptionsDebounce();
      },
      { immediate: true }
    );

    onUnmounted(() => {
      cleanup?.();
    });

    function getSearchFavoriteOptions() {
      const favoriteOptions$ = [];
      if (props.queryString && !/^\s*$/.test(props.queryString)) {
        const keyword = props.queryString.replace(/^\s+|\s+$/g, '').toLocaleLowerCase();
        for (const item of props.favoriteList) {
          const content = item?.config?.queryParams?.query || '';
          if (content?.toLocaleLowerCase().includes(keyword)) {
            favoriteOptions$.push({
              title: `${item.name} / ${item.name}`,
              content,
              keyword,
            });
          }
        }
      }
      favoriteOptions.value = favoriteOptions$;
    }

    async function handleGetOptions() {
      pageInit();
      cursorIndex.value = -1;
      let fieldItem: IFilterField = null;
      for (const item of props.fields) {
        if (item.name === props.field) {
          fieldItem = item;
          break;
        }
      }
      if (props.type === EQueryStringTokenType.key) {
        localOptions.value = props.fields
          .filter(item => {
            if (!props.search) {
              return true;
            }
            if (item.alias.toLocaleLowerCase().includes(props.search.toLocaleLowerCase())) {
              return true;
            }
            if (item.name.toLocaleLowerCase().includes(props.search.toLocaleLowerCase())) {
              return true;
            }
            return false;
          })
          .map(item => ({
            id: item.name,
            name: item.name,
          }));
      } else if (props.type === EQueryStringTokenType.method) {
        localOptions.value = getQueryStringMethods(fieldItem?.type).map(item => ({
          id: item.id,
          name: item.id,
          desc: item.name,
        }));
      } else if (props.type === EQueryStringTokenType.value) {
        if (fieldItem?.isEnableOptions) {
          if (!loading.value) {
            // const data = await getValueData(false, !!fieldItem?.is_dimensions);
            const data = await getValueData(false);
            localOptions.value = data;
          }
        } else {
          localOptions.value = [];
        }
      } else if (props.type === EQueryStringTokenType.condition) {
        localOptions.value = QUERY_STRING_CONDITIONS.map(item => ({
          id: item.id,
          name: item.id,
          desc: item.name,
        }));
      }
    }
    function handleGetOptionsProxy() {
      if (props.type === EQueryStringTokenType.value) {
        handleGetOptionsDebounce();
      } else {
        handleGetOptions();
      }
    }
    function handleKeydownEvent(event: KeyboardEvent) {
      switch (event.key) {
        case 'ArrowUp': {
          // 按下上箭头键
          event.preventDefault();
          cursorIndex.value -= 1;
          if (cursorIndex.value < -1) {
            cursorIndex.value = localOptions.value.length - 1;
          }
          updateSelection();
          break;
        }

        case 'ArrowDown': {
          event.preventDefault();
          cursorIndex.value += 1;
          if (cursorIndex.value > localOptions.value.length) {
            cursorIndex.value = 0;
          }
          updateSelection();
          break;
        }
        case 'Enter': {
          event.preventDefault();
          enterSelection();
          break;
        }
      }
    }
    function enterSelection() {
      const item = localOptions.value[cursorIndex.value];
      if (item) {
        emit('select', item.id);
      }
    }
    function handleSelect(str: string) {
      emit('select', str);
    }
    function updateSelection() {
      const listEl = elRef.value?.querySelector('.wrap-left .options-wrap');
      const el = listEl?.children?.[cursorIndex.value] as HTMLDivElement;
      el?.focus();
    }
    /**
     * @description 搜索接口
     * @param item
     * @param method
     * @param value
     */
    async function getValueData(isScroll = false, _isDimensions = false) {
      let list = [];
      if (isScroll) {
        scrollLoading.value = true;
      } else {
        loading.value = true;
      }

      if (props.field) {
        const limit = page.value * pageSize.value;
        const data = await props.getValueFn({
          // queryString: `${isDimensions ? 'dimensions.' : ''}${props.field} : ${props.search || '*'}`,
          // fields: [props.field],
          // limit: limit,
          where: props.search
            ? [
                {
                  key: props.field,
                  operator: 'like',
                  value: [props.search],
                },
              ]
            : [],
          limit: limit,
          fields: [props.field],
        });
        isEnd.value = limit > data.count;
        list = data.list;
      }
      loading.value = false;
      scrollLoading.value = false;
      return list;
    }
    function pageInit() {
      page.value = 1;
      isEnd.value = false;
    }

    async function handleScroll() {
      const container = optionsRef.value;
      const scrollTop = container.scrollTop;
      const clientHeight = container.clientHeight;
      const scrollHeight = container.scrollHeight;
      if (scrollTop + clientHeight >= scrollHeight - 3) {
        if (!scrollLoading.value && !isEnd.value && props.type === EQueryStringTokenType.value) {
          scrollLoading.value = true;
          page.value += 1;
          const data = await getValueData(true);
          localOptions.value = data;
          scrollLoading.value = false;
        }
      }
    }
    function handleSelectFavorite(item) {
      emit('selectFavorite', item.content);
    }
    function getSubtitle(id: string) {
      if ([EQueryStringTokenType.method, EQueryStringTokenType.condition].includes(props.type)) {
        const items = qsSelectorOptionsDescMap?.[id] || [];
        return (
          <span class='subtitle-text'>
            {items.map(item => {
              if (item.type === 'text') {
                return item.text;
              }
              if (item.type === 'tag') {
                return <span class='subtitle-text-tag'>{item.text}</span>;
              }
            })}
          </span>
        );
      }
      return undefined;
    }

    return {
      loading,
      localOptions,
      cursorIndex,
      scrollLoading,
      favoriteOptions,
      handleScroll,
      handleSelect,
      getSubtitle,
      handleSelectFavorite,
      t,
    };
  },
  render() {
    const optionName = (item: { id: string; name: string }) => {
      if (item.id === '') {
        return '--';
      }
      if (item.name) {
        if (item.id === item.name) {
          return item.id;
        }
        return `${item.name} (${item.id})`;
      }
      return item.id;
    };
    return (
      <div
        ref='el'
        class='vue3_retrieval-filter__qs-selector-options-component'
      >
        <div class='wrap-left'>
          <div
            ref='options'
            class='options-wrap'
            onScroll={this.handleScroll}
          >
            {this.loading
              ? new Array(3).fill(null).map((_item, index) => (
                  <div
                    key={index}
                    class='option-item skeleton-item'
                  >
                    <div class='skeleton-element h-16' />
                  </div>
                ))
              : this.localOptions.map((item, index) => (
                  <div
                    key={item.id}
                    class={['option-item main-item', { 'cursor-active': index === this.cursorIndex }]}
                    tabindex={0}
                    onClick={e => {
                      e.stopPropagation();
                      this.handleSelect(item.id);
                    }}
                  >
                    <span
                      style={{
                        backgroundColor: queryStringColorMap[this.type]?.background || '#E6F2F1',
                        color: queryStringColorMap[this.type]?.color || '#02776E',
                      }}
                      class='option-item-icon'
                    >
                      <span class={['icon-monitor', queryStringColorMap[this.type]?.icon || '']} />
                    </span>
                    <span class='option-item-name'>{optionName(item)}</span>
                    {this.getSubtitle(item.id)}
                  </div>
                ))}
            {this.scrollLoading && (
              <div class='option-item  scroll-loading'>
                <img
                  alt=''
                  src={loadingImg}
                />
              </div>
            )}
          </div>
          <div class='favorite-wrap'>
            <div class='favorite-wrap-title'>
              <i18n-t keypath={'联想到以下 {0} 个收藏：'}>
                <span class='favorite-count'>{this.favoriteOptions.length}</span>
              </i18n-t>
            </div>
            {this.favoriteOptions.length ? (
              this.favoriteOptions.map((item, index) => (
                <div
                  key={index}
                  class='favorite-item'
                  onClick={e => {
                    e.stopPropagation();
                    this.handleSelectFavorite(item);
                  }}
                >
                  <span class='favorite-item-name'>{item.title}</span>
                  <span class='favorite-item-content'>
                    <TextHighlighter
                      content={item.content}
                      keyword={item.keyword}
                    />
                  </span>
                </div>
              ))
            ) : (
              <EmptyStatus
                textMap={{
                  empty: this.t('暂未匹配到符合条件的收藏项'),
                }}
                type={'empty'}
              />
            )}
          </div>
          <div class='key-help'>
            <span class='desc-item'>
              <span class='desc-item-icon mr-2'>
                <span class='icon-monitor icon-mc-arrow-down up' />
              </span>
              <span class='desc-item-icon'>
                <span class='icon-monitor icon-mc-arrow-down' />
              </span>
              <span class='desc-item-name'>{this.t('移动光标')}</span>
            </span>
            <span class='desc-item'>
              <span class='desc-item-box'>Enter</span>
              <span class='desc-item-name'>{this.t('确认结果')}</span>
            </span>
          </div>
        </div>
        <div class='wrap-right'>
          <QsSelectorHelp />
        </div>
      </div>
    );
  },
});
