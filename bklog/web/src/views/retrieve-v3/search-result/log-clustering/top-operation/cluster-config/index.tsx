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

import { defineComponent, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
import EditConfig from './edit-config';
import './index.scss';

export default defineComponent({
  name: 'ClusterConfig',
  components: {
    EditConfig,
  },
  props: {
    indexId: {
      type: String,
      require: true,
    },
    totalFields: {
      type: Array,
      default: () => [],
    },
  },
  setup(props, { expose }) {
    const { t } = useLocale();

    const showEditConfig = ref(false);

    const handleShowEditConfig = () => {
      showEditConfig.value = true;
    };

    const handleBeforeClose = () => {
      setTimeout(() => {
        showEditConfig.value = false;
      });
    };

    expose({
      show: handleShowEditConfig,
    });

    return () => (
      <div
        class='cluster-config-operate-main'
        on-click={handleShowEditConfig}
      >
        <log-icon
          type='setting-line'
          class='icon'
        />
        <span>{t('聚类设置')}</span>
        <bk-sideslider
          is-show={showEditConfig.value}
          before-close={handleBeforeClose}
          quick-close={true}
          width={1140}
          title={t('聚类设置')}
        >
          <div slot='content'>
            <edit-config
              indexId={props.indexId}
              totalFields={props.totalFields}
              on-close={() => (showEditConfig.value = false)}
            />
          </div>
        </bk-sideslider>
      </div>
    );
  },
});
