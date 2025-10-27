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

import { computed, defineComponent } from 'vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute, useRouter } from 'vue-router/composables';
import EmptyStatus from '@/components/empty-status/index.vue';
import './index.scss';

export default defineComponent({
  name: 'ClusterEmpty',
  components: {
    EmptyStatus,
  },
  props: {
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const collectorConfigId = computed(() => store.state.indexSetFieldConfig.clean_config.extra?.collector_config_id);
    const indexSetItem = computed(() => store.state.indexItem);
    const isHaveAnalyzed = computed(() => (store.state.indexFieldInfo.fields || []).some(item => item.is_analyzed));
    const exhibitText = computed(() =>
      collectorConfigId.value ? t('当前无可用字段，请前往日志清洗进行设置') : t('当前索引集不支持日志聚类设置'),
    );
    const exhibitOperate = computed(() => (collectorConfigId.value ? t('跳转到日志清洗') : ''));

    const handleLeaveCurrent = () => {
      // 不显示字段提取时跳转计算平台
      if (indexSetItem.value?.scenario_id !== 'log' && !isHaveAnalyzed.value) {
        const jumpUrl = `${window.BKDATA_URL}`;
        window.open(jumpUrl, '_blank');
        return;
      }
      // 无清洗 去清洗
      if (!!collectorConfigId.value) {
        router.push({
          name: 'clean-edit',
          params: { collectorId: collectorConfigId.value },
          query: {
            spaceUid: store.state.spaceUid,
            backRoute: route.name,
          },
        });
      }
    };

    return () => (
      <div>
        {props.clusterSwitch && (
          <bk-alert
            title={t('日志聚类必需至少有一个text类型的字段，当前无该字段类型，请前往日志清洗进行设置。')}
            type='info'
            closable
          />
        )}
        <bk-table
          class='no-text-table'
          data={[]}
        >
          <div slot='empty'>
            <empty-status
              class='empty-text'
              show-text={false}
              empty-type='empty'
            >
              {indexSetItem.value?.scenario_id !== 'log' && !isHaveAnalyzed.value ? (
                <p>
                  <i18n path='无分词字段 请前往 {0} 调整清洗'>
                    <span
                      class='empty-leave'
                      on-click={handleLeaveCurrent}
                    >
                      {t('计算平台')}
                    </span>
                  </i18n>
                </p>
              ) : (
                <div>
                  <p>{exhibitText}</p>
                  <span
                    class='empty-leave'
                    on-click={handleLeaveCurrent}
                  >
                    {exhibitOperate}
                  </span>
                </div>
              )}
            </empty-status>
          </div>
        </bk-table>
      </div>
    );
  },
});
