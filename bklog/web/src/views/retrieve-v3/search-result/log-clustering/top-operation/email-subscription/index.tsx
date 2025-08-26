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

import { computed, defineComponent, onMounted, ref } from 'vue';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';
import { debounce } from 'throttle-debounce';
import $http from '@/api';
import useLocale from '@/hooks/use-locale';
import CreateSubscription from './create-subscription';

import './index.scss';

export default defineComponent({
  name: 'EmailSubscription',
  components: {
    CreateSubscription,
  },
  props: {
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props) {
    const store = useStore();
    const route = useRoute();
    const { t } = useLocale();

    const isCurrentIndexSetIdCreateSubscription = ref(false);
    const isShowQuickCreateSubscriptionDrawer = ref(false);

    const bkBizId = computed(() => store.state.bkBizId);

    const goToMySubscription = () => {
      window.bus.$emit('showGlobalDialog');
    };

    /**
     * 检查当前 索引集 是否创建过订阅。
     */
    const checkReportIsExisted = () => {
      $http
        .request('newReport/getExistReports/', {
          query: {
            scenario: 'clustering',
            bk_biz_id: bkBizId.value,
            index_set_id: window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId,
          },
        })
        .then(response => {
          isCurrentIndexSetIdCreateSubscription.value = !!response.data.length;
        })
        .catch(e => console.error(e));
    };

    const checkReportIsExistedDebounce = debounce(1000, checkReportIsExisted);

    onMounted(() => {
      if (!props.isClusterActive) {
        return;
      }

      checkReportIsExistedDebounce();
    });

    return () => (
      <div class='email-subscription-main'>
        {isCurrentIndexSetIdCreateSubscription.value ? (
          <bk-dropdown-menu
            ref='refOfSubscriptionDropdown'
            align='right'
            trigger='click'
          >
            <div slot='dropdown-trigger'>
              <div class='email-subscription'>
                <log-icon
                  type='email'
                  common
                  v-bk-tooltips={t('已订阅当前页面')}
                  class={{ 'is-subscribed': isCurrentIndexSetIdCreateSubscription.value }}
                />
              </div>
            </div>
            <div slot='dropdown-content'>
              <div class='dropdown-list'>
                <div
                  class='item'
                  on-click={() => (isShowQuickCreateSubscriptionDrawer.value = true)}
                >
                  <log-icon
                    type='circle-add'
                    class='item-icon'
                  />
                  <span class='item-title'>{t('新建订阅')}</span>
                </div>
                <div
                  class='item'
                  on-click={goToMySubscription}
                >
                  <log-icon
                    type='overview-table'
                    class='item-icon'
                  />
                  <span class='item-title'>{t('我的订阅')}</span>
                </div>
              </div>
            </div>
          </bk-dropdown-menu>
        ) : (
          <div
            class='email-subscription'
            on-click={() => (isShowQuickCreateSubscriptionDrawer.value = true)}
          >
            <log-icon
              common
              type='email'
              v-bk-tooltips={t('邮件订阅')}
            />
          </div>
        )}
        <create-subscription
          value={isShowQuickCreateSubscriptionDrawer.value}
          index-id={props.indexId}
          scenario='clustering'
          on-change={value => (isShowQuickCreateSubscriptionDrawer.value = value)}
        />
      </div>
    );
  },
});
