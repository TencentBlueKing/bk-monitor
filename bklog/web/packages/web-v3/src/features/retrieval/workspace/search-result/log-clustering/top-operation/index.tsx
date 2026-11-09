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

import { Tag as TTag } from 'tdesign-vue-next';
import { includesValue } from '@/shared/utils/typed-record';

import { computed, defineComponent, ref } from 'vue';
import Stratege from './strategy/index';
import QuickFilter from './quick-filter/index';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import EmailSubscription from './email-subscription/index';
import ClusterConfig from './cluster-config/index';
import ClusterDownload from './cluster-download/index';

import './index.scss';

export default defineComponent({
  emits: ["close-group-tag","closeGroupTag","close-year-tag","closeYearTag","handle-finger-operate","handleFingerOperate"],

  name: 'TopOperation',
  components: {
    EmailSubscription,
    Stratege,
    QuickFilter,
    ClusterConfig,
    ClusterDownload,
  },
  props: {
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    isShowClusterStep: {
      type: Boolean,
      default: true,
    },
    fingerOperateData: {
      type: Object,
      require: true,
    },
    requestData: {
      type: Object,
      require: true,
    },
    totalFields: {
      type: Array,
      require: true,
    },
    indexId: {
      type: String,
      require: true,
    },
    logTableRef: {
      type: Object,
      default: null,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const clusterConfigRef = ref<any>(null);
    /** 是否创建过策略 */
    const strategyHaveSubmit = ref(false);

    const getDimensionStr = computed(() =>
      props.fingerOperateData?.dimensionList.length
        ? `${t('聚合维度')} : ${props.fingerOperateData.dimensionList.join(', ')}`
        : '',
    );
    const getGroupStr = computed(() =>
      props.fingerOperateData?.selectGroupList.length
        ? `${t('分组')} : ${props.fingerOperateData.selectGroupList.join(', ')}`
        : '',
    );
    const getYearStr = computed(() =>
      props.requestData?.year_on_year_hour ? `${t('同比')} : ${props.requestData.year_on_year_hour}h` : '',
    );

    const isShowGroupTag = computed(
      () =>
        props.clusterSwitch &&
        !props.isShowClusterStep &&
        (getGroupStr.value || getDimensionStr.value || getYearStr.value),
    );

    const isExternal = window.IS_EXTERNAL === true;

    // PO 环境进入聚类设置需同时具备 log_search 与 log_clustering。
    // 只授聚类配置不能隐式获得检索权；只授检索能看结果但看不到设置入口。
    // externalPermissions 在空间加载完成后才写入，不能在 setup 里取一次快照
    const isClusterConfigVisible = computed(() => {
      if (!isExternal) {
        return true;
      }
      const permissions = store.state.externalPermissions ?? [];
      return includesValue(permissions, 'log_search') && includesValue(permissions, 'log_clustering');
    });

    const handleStrategySubmitStatus = (v: boolean) => {
      strategyHaveSubmit.value = v;
    };

    const handleCloseGroupTag = () => {
      emit('close-group-tag');
    };
    const handleCloseYearTag = () => {
      emit('close-year-tag');
    };

    const handleFingerOperate = (operateType: string, val: any, isQuery: boolean) => {
      emit('handle-finger-operate', operateType, val, isQuery);
    };

    expose({
      openClusterConfig: () => clusterConfigRef.value?.show(),
    });

    return () => (
      <div class='clustering-nav'>
        <div class='operations-main'>
          <stratege
            indexId={props.indexId}
            cluster-switch={props.clusterSwitch}
            is-cluster-active={props.isClusterActive}
            strategy-submit-status={handleStrategySubmitStatus}
          />
          <div class='right-operation-main'>
            <QuickFilter
              indexId={props.indexId}
              fingerOperateData={props.fingerOperateData}
              requestData={props.requestData}
              totalFields={props.totalFields}
              clusterSwitch={props.clusterSwitch}
              strategyHaveSubmit={strategyHaveSubmit.value}
              isClusterActive={props.isClusterActive}
              onHandleFingerOperate={handleFingerOperate}
            />
            {!isExternal && (
              <email-subscription
                style='margin: 0 8px'
                indexId={props.indexId}
                isClusterActive={props.isClusterActive}
              />
            )}
            <ClusterDownload
              style='margin-right: 8px'
              indexId={props.indexId}
              isClusterActive={props.isClusterActive}
              logTableRef={props.logTableRef}
            />
            {isClusterConfigVisible.value && (
              <ClusterConfig
                ref={clusterConfigRef}
                indexId={props.indexId}
                totalFields={props.totalFields}
                isExternal={isExternal}
              />
            )}
          </div>
        </div>
        {isShowGroupTag.value && (
          <div class='tags-main'>
            {getDimensionStr.value && <TTag variant={"outline"} data-v2-display='tag'>{getDimensionStr.value}</TTag>}
            {getGroupStr.value && (
              <TTag
                variant={"outline"}
                closable
                onClose={handleCloseGroupTag} data-v2-display='tag'
              >
                {getGroupStr.value}
              </TTag>
            )}
            {getYearStr.value && (
              <TTag
                variant={"outline"}
                closable
                onClose={handleCloseYearTag} data-v2-display='tag'
              >
                {getYearStr.value}
              </TTag>
            )}
          </div>
        )}
      </div>
    );
  },
});
