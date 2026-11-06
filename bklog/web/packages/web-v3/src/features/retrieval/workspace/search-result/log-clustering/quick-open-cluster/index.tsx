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

import { Button as TButton } from 'tdesign-vue-next';
import { defineComponent, ref } from 'vue';
import useLocale from '@/shared/composables/use-locale';
import clusterImg from '@/shared/assets/images/cluster-img/cluster.png';
import ClusterAccess from './cluster-access/index';

import './index.scss';

export default defineComponent({
  emits: ["create-cluster","createCluster"],

  name: 'QuickOpenCluster',
  components: {
    ClusterAccess,
  },
  props: {
    indexSetId: {
      type: String,
      default: '',
    },
    totalFields: {
      type: Array<any>,
      required: true,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const isShowDialog = ref(false);

    const handleAccessCluster = () => {
      isShowDialog.value = true;
    };

    return () => (
      <div class='quick-open-cluster-container'>
        <div class='left-box'>
          <h2>{t('快速开启日志聚类')}</h2>
          <p>{t('日志聚类可以通过智能分析算法，将相似度高的日志进行快速的汇聚分析，提取日志 Pattern 并进行展示')}</p>
          <h3>{t('日志聚类的优势')}</h3>
          <p>1. {t('有利于发现日志中的规律和共性问题，方便从海量日志中排查问题，定位故障')}</p>
          <p>2. {t('可从海量日志中，提取共性部分同时保留独立信息以便于减少存储成本，最多可减少 10% 的存储成本')}</p>
          <p>3. {t('当版本变更时，可快速定位变更后新增问题')}</p>
          <TButton
            style='margin-top: 32px;'
            theme='primary'
            onClick={handleAccessCluster}
          >
            {t('接入日志聚类')}
          </TButton>
        </div>
        <div class='right-box'>
          <img src={clusterImg} />
        </div>
        <ClusterAccess
          totalFields={props.totalFields}
          isShow={isShowDialog.value}
          indexSetId={props.indexSetId}
          onClose={() => (isShowDialog.value = false)}
          onSuccess={() => emit('create-cluster')}
        />
      </div>
    );
  },
});
