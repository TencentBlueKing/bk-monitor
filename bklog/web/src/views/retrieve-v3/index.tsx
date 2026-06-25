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

import { computed, defineAsyncComponent, defineComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { BK_LOG_STORAGE } from '../../store/store.type';
import V3Container from './container';
import V3Collection from './favorite';
import SceneFilter from './search-bar/scene-filter';
import V3Searchbar from './search-bar';
import V3SearchResult from './search-result';
import V3Toolbar from './toolbar';
import useAppInit from './use-app-init';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';

import './global-en.scss';
import './index.scss';
import './media.scss';
import './segment-pop.scss';

let aiAssitantModulePromise: Promise<any> | null = null;

const loadAiAssitantModule = () => {
  if (!aiAssitantModulePromise) {
    aiAssitantModulePromise = import(/* webpackChunkName: 'retrieve-ai-assistant' */ '@/global/ai-assitant/index');
  }

  return aiAssitantModulePromise;
};

const AiAssitant = defineAsyncComponent(loadAiAssitantModule);

const scheduleIdleTask = (callback: () => void, timeout = 4000) => {
  if (typeof window === 'undefined') {
    return undefined;
  }

  if ('requestIdleCallback' in window) {
    return window.requestIdleCallback(callback, { timeout });
  }

  return window.setTimeout(callback, Math.min(timeout, 2000));
};

const cancelIdleTask = (taskId?: number) => {
  if (typeof taskId !== 'number' || typeof window === 'undefined') {
    return;
  }

  if ('cancelIdleCallback' in window) {
    window.cancelIdleCallback(taskId);
    return;
  }

  window.clearTimeout(taskId);
};

export default defineComponent({
  name: 'RetrieveV3',
  setup() {
    const store = useStore();
    const { t } = useLocale();
    const aiAssitantRef = RetrieveHelper.aiAssitantHelper.getAiAssitantInstance();
    const shouldMountAiAssitant = ref(false);
    let aiPreloadIdleTask: number | undefined;
    let aiPreloadDelayTimer: ReturnType<typeof setTimeout> | undefined;

    const preloadAiAssitant = () => {
      if (!store.state.features.isAiAssistantActive) {
        return;
      }

      loadAiAssitantModule().catch((error) => {
        console.warn('[RetrieveV3] preload ai assistant failed', error);
        aiAssitantModulePromise = null;
      });
    };

    const scheduleAiAssitantPreload = () => {
      if (!store.state.features.isAiAssistantActive || aiPreloadDelayTimer || aiPreloadIdleTask) {
        return;
      }

      aiPreloadDelayTimer = window.setTimeout(() => {
        aiPreloadDelayTimer = undefined;
        aiPreloadIdleTask = scheduleIdleTask(() => {
          aiPreloadIdleTask = undefined;
          preloadAiAssitant();
        }, 5000);
      }, 3000);
    };

    RetrieveHelper.aiAssitantHelper.setAiAssitantMountLoader(async () => {
      await loadAiAssitantModule();
      shouldMountAiAssitant.value = true;
      await nextTick();
    });

    onBeforeUnmount(() => {
      RetrieveHelper.aiAssitantHelper.setAiAssitantMountLoader(undefined);
      cancelIdleTask(aiPreloadIdleTask);
      if (aiPreloadDelayTimer) {
        window.clearTimeout(aiPreloadDelayTimer);
      }
    });

    const {
      isSearchContextStickyTop,
      isSearchResultStickyTop,
      stickyStyle,
      contentStyle,
      isPreApiLoaded,
    } = useAppInit();

    const isStartTextEllipsis = computed(() => store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR] === 'start');
    const isSceneMode = computed(() => store.getters.isSceneMode);
    const isSceneLoading = computed(
      () => store.state.indexFieldInfo.is_loading || store.state.indexSetQueryResult.is_loading,
    );

    // 追踪字段列表是否完成过至少一次请求（is_loading 从 true → false）
    const isFieldListFetched = ref(false);
    watch(
      () => store.state.indexFieldInfo.is_loading,
      (loading, prevLoading) => {
        if (prevLoading && !loading) {
          isFieldListFetched.value = true;
        }
      },
    );
    // 切换检索模式或场景时，重置字段列表获取状态
    watch(
      () => store.state.indexItem.retrieve_type,
      () => {
        isFieldListFetched.value = false;
      },
    );
    watch(
      () => store.state.indexItem.scene_active,
      () => {
        isFieldListFetched.value = false;
      },
    );

    watch(
      () => [store.state.features.isAiAssistantActive, isPreApiLoaded.value],
      ([isAiAssistantActive, isLoaded]) => {
        if (isAiAssistantActive && isLoaded) {
          scheduleAiAssitantPreload();
        }
      },
      { immediate: true },
    );

    // 字段列表已请求完成但返回为空
    const isFieldListEmpty = computed(
      () => isFieldListFetched.value
        && store.state.indexFieldInfo.fields?.length === 0,
    );

    /**
     * AI 助手关闭
     */
    const handleAiClose = () => {
      RetrieveHelper.fire(RetrieveEvent.AI_CLOSE);
    };

    /**
     * 渲染 AI 助手
     * @returns
     */
    const renderAiAssitant = () => {
      if (!store.state.features.isAiAssistantActive || !shouldMountAiAssitant.value) {
        return null;
      }

      return <AiAssitant ref={aiAssitantRef} on-close={handleAiClose}></AiAssitant>;
    };

    /**
     * 渲染结果内容
     * @returns
     */
    const renderSearchBar = () => {
      const stickyClass = {
        'is-sticky-top': isSearchContextStickyTop.value,
        'is-sticky-top-result': isSearchResultStickyTop.value,
      };

      if (isSceneMode.value) {
        return <SceneFilter isSticky={isSearchContextStickyTop.value} />;
      }

      return <V3Searchbar class={stickyClass} />;
    };

    /**
     * 渲染场景化检索空状态提示
     */
    const renderSceneEmptyTip = () => (
      <div class='scene-empty-tip' v-bkloading={{ isLoading: isSceneLoading.value }}>
        <bk-exception class='exception-wrap-item' type='search-empty' scene='part'>
          <h1 class='scene-empty-tip-title'>{t('当前日志未过滤')}</h1>
          <div class='scene-empty-tip-desc'>
            {t('请先按照标签过滤日志范围后，再进行日志检索')}
          </div>
          <div class='scene-empty-tip-detail'>
            {t('场景化检索默认搜索全量日志，为保证检索体验及集群稳定性，请通过顶部标签过滤数据后查看日志。可随时修改标签过滤内容')}
          </div>
        </bk-exception>
      </div>
    );

    /**
     * 渲染字段列表为空时的提示（未匹配到索引集）
     */
    const renderFieldEmptyTip = () => (
      <div class='scene-empty-tip' v-bkloading={{ isLoading: isSceneLoading.value }}>
        <bk-exception class='exception-wrap-item' type='search-empty' scene='part'>
          <h1 class='scene-empty-tip-title'>{t('未匹配到索引集')}</h1>
          <div class='scene-empty-tip-desc'>
            {t('根据过滤条件未匹配到索引集，请修改过滤条件')}
          </div>
          <div class='scene-empty-tip-detail'>
            {t('若仍无结果返回，可点击联系')}
            <a class='segment-span-tag' href={'wxwork://message/?username=BK助手'}>{t('BK助手')}</a>
          </div>
        </bk-exception>
      </div>
    );

    const renderResultContent = () => {
      if (isPreApiLoaded.value) {
        // 场景化模式下渲染逻辑：
        // 1. 字段列表未获取 → 显示 renderSceneEmptyTip，隐藏检索结果
        // 2. 字段列表已获取但为空 → 显示 renderFieldEmptyTip，隐藏检索结果
        // 3. 字段列表已获取且有数据 → 显示检索结果
        const showSceneEmptyTip = isSceneMode.value && !isFieldListFetched.value;
        const showFieldEmptyTip = isSceneMode.value && isFieldListEmpty.value;
        const hideSearchResult = isSceneMode.value && (!isFieldListFetched.value || isFieldListEmpty.value);

        return [
          <V3Toolbar></V3Toolbar>,
          <V3Container>
            {renderSearchBar()}
            <V3SearchResult v-show={!hideSearchResult}></V3SearchResult>
            {showSceneEmptyTip && renderSceneEmptyTip()}
            {showFieldEmptyTip && renderFieldEmptyTip()}
          </V3Container>,
        ];
      }

      return <div style={{ minHeight: '50vh', width: '100%' }}></div>;
    };

    /**
     * 渲染根元素
     * @returns
     */
    return () => (
      <div
        style={stickyStyle.value}
        class={[
          'v3-bklog-root',
          { 'is-start-text-ellipsis': isStartTextEllipsis.value },
          { 'is-sticky-top': isSearchContextStickyTop.value, 'is-sticky-top-result': isSearchResultStickyTop.value },
          { 'is-scene-mode': isSceneMode.value },
        ]}
        v-bkloading={{ isLoading: !isPreApiLoaded.value }}
      >
        <V3Collection></V3Collection>
        <div
          style={contentStyle.value}
          class='v3-bklog-content'
        >
          {renderResultContent()}
          {renderAiAssitant()}
        </div>
      </div>
    );
  },
});
