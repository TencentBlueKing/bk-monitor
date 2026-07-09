/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, computed, defineComponent, onActivated, shallowRef } from 'vue';

import { Button, InfoBox } from 'bkui-vue';
import { getDocLink } from 'monitor-api/modules/commons';
import { useAppStore } from 'trace/store/modules/app';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import type { IBtnAndLinkItem, SpaceIntroduceKeys } from './typing';

import './guide-page.scss';

const SPACE_DEMO_NAME = 'DEMO';

export default defineComponent({
  name: 'GuidePage',
  props: {
    marginLess: {
      default: false,
      type: Boolean,
    },
    guideId: {
      type: String,
      required: false,
    },
    introduceData: {
      type: Object,
      default: () => null,
    },
    customEventUrls: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: {
    url: (_url: string) => true,
  },
  setup(props, { emit }) {
    const navId = shallowRef<'' | SpaceIntroduceKeys | unknown>('');
    const route = useRoute();
    const appStore = useAppStore();
    const { t } = useI18n();
    const bizId = computed(() => {
      return appStore.bizId;
    });
    const bizList = computed(() => {
      return appStore.bizList;
    });
    const demoBiz = computed(() => {
      return bizList.value.find(item => item.is_demo);
    });
    navId.value = route.meta?.navId || '';
    onActivated(() => {
      navId.value = route.meta?.navId || '';
    });

    const handleGotoLink = (item: IBtnAndLinkItem) => {
      if (item.url?.match?.(/^https?:\/\//)) {
        window.open(item.url, '_blank');
        return;
      }
      getDocLink({ md_path: item.url })
        .then(data => {
          window.open(data, '_blank');
        })
        .catch(() => false);
    };
    const handleBtnClick = (item: IBtnAndLinkItem) => {
      if (item.name === SPACE_DEMO_NAME) {
        if (demoBiz.value?.bk_biz_id) {
          if (+appStore.bizId === +demoBiz.value?.bk_biz_id) {
            location.reload();
          } else {
            location.href = location.href.replace(`bizId=${bizId.value}`, `bizId=${demoBiz.value?.bk_biz_id}`);
          }
        }
      } else if (props.introduceData.is_no_source) {
        InfoBox({
          title: t('当前未关联任何资源'),
          subTitle: t('该功能暂不可用'),
        });
      } else if (item.url.match(/^#\//)) {
        // 新建apm改为抽屉方式
        if (props.customEventUrls.some(url => item.url.includes(url))) {
          emit('url', item.url);
          return;
        }
        location.href = location.href.replace(location.hash, item.url);
        // this.$router.push({ path: item.url.replace('#/', '') });
      } else if (item.url) {
        window.open(item.url, '_blank');
      }
    };
    return {
      t,
      demoBiz,
      navId,
      handleBtnClick,
      handleGotoLink,
    };
  },
  render() {
    if (!this.introduceData) return undefined;
    const { title = '', subTitle = '', introduce = [], buttons = [], links = [] } = this.introduceData?.data || {};
    return (
      <div class={['guide-page-wrap-vue3', { 'margin-less': this.marginLess }]}>
        <div class='guide-page-main'>
          <div class='guide-left'>
            <div class='guide-title'>{this.t(title)}</div>
            {subTitle && <div class='guide-subtitle'>{this.t(subTitle)}</div>}
            <ul class='guide-tips'>
              {introduce.map((item, index) => (
                <li
                  key={index}
                  class='guide-tips-item'
                >
                  {index + 1}. {this.t(item)}
                </li>
              ))}
            </ul>
            <div class='guide-btn-group'>
              {buttons.map(item =>
                !(item.name === SPACE_DEMO_NAME && !this.demoBiz) ? (
                  <Button
                    key={item.name}
                    theme={item.name === SPACE_DEMO_NAME ? undefined : 'primary'}
                    onClick={() => this.handleBtnClick(item)}
                  >
                    {this.$t(item.name)}
                  </Button>
                ) : undefined
              )}
            </div>
            {links?.length > 0 && (
              <div class='guide-link'>
                <div class='link-title'>{this.$t('文档链接')}</div>
                <div class='link-list'>
                  {links.map(item =>
                    item.url ? (
                      <span
                        key={item.name}
                        class='link-item'
                        onClick={() => this.handleGotoLink(item)}
                      >
                        {this.$t(item.name)}
                      </span>
                    ) : undefined
                  )}
                </div>
              </div>
            )}
          </div>
          <div class='guide-right'>
            <div class={`guide-img-wrap img-${this.guideId ?? this.navId}`} />
          </div>
        </div>
      </div>
    );
  },
});
