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

import { defineComponent } from 'vue';
import { Drawer as TDrawer } from 'tdesign-vue-next';
import useDialogVisible from '@/shared/global/overlay/use-dialog-visible';
import useLocale from '@/shared/composables/use-locale';
import EditConfig from './edit-config/index';
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
    isExternal: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { expose }) {
    const { t } = useLocale();

    const { visible: showEditConfig, zIndex, setVisible } = useDialogVisible(false, { type: 'slider' });

    const handleShowEditConfig = () => {
      setVisible(true);
    };

    const handleBeforeClose = () => {
      setTimeout(() => {
        setVisible(false);
      });
    };

    expose({
      show: handleShowEditConfig,
    });

    return () => (
      <div class='cluster-config-operate-main' onClick={handleShowEditConfig}>
        <log-icon type='setting-line' class='icon' />
        <span>{t('聚类设置')}</span>
        <TDrawer
          visible={showEditConfig.value}
          size='1140px'
          attach='body'
          zIndex={zIndex.value}
          footer={false}
          closeBtn={false}
          closeOnOverlayClick={true}
          closeOnEscKeydown={false}
          drawerClassName='cluster-settings-drawer'
          onClose={handleBeforeClose}
          v-slots={{
            header: () => (
              <div class='cluster-settings-header'>
                <button type='button' aria-label={t('关闭')} onClick={handleBeforeClose}>
                  <log-icon common type='angle-right' />
                </button>
                <span>{t('聚类设置')}</span>
              </div>
            ),
            body: () =>
              showEditConfig.value ? (
                <EditConfig
                  indexId={props.indexId}
                  totalFields={props.totalFields}
                  isExternal={props.isExternal}
                  onClose={() => setVisible(false)}
                />
              ) : null,
          }}
        />
      </div>
    );
  },
});
