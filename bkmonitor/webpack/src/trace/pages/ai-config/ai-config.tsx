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
import { defineComponent, shallowRef, useTemplateRef } from 'vue';

import { Button, InfoBox, Tab } from 'bkui-vue';
import { useI18n } from 'vue-i18n';
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';

import AnomalyDetection from './components/anomaly-detection/anomaly-detection';
import SourceCodeAnalysis from './components/source-code-analysis/source-code-analysis';
import { EAiConfigTab } from './typings';

import './ai-config.scss';

/**
 * @description AI 设置：异常检测与源码 AI 分析的配置入口
 */
export default defineComponent({
  name: 'AiConfig',
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();

    /** 当前 Tab 由 url query 决定，保证刷新与分享后仍停留在同一 Tab */
    const activeTab = shallowRef(
      route.query.tab === EAiConfigTab.sourceCodeAnalysis
        ? EAiConfigTab.sourceCodeAnalysis
        : EAiConfigTab.anomalyDetection
    );

    /** 当前激活 Tab 对应的子组件 ref，用于在路由离开时调用其暴露的 save / isEdited */
    const anomalyDetectionRef = useTemplateRef<InstanceType<typeof AnomalyDetection>>('anomalyDetection');
    const sourceCodeAnalysisRef = useTemplateRef<InstanceType<typeof SourceCodeAnalysis>>('sourceCodeAnalysis');

    const handleTabChange = (tab: string) => {
      activeTab.value = tab as EAiConfigTab;
      router.replace({ query: { ...route.query, tab } });
    };

    /**
     * @description 获取当前激活 Tab 对应的子组件实例（包含 isEdited / save）
     */
    const getActiveChild = () => {
      return activeTab.value === EAiConfigTab.sourceCodeAnalysis
        ? sourceCodeAnalysisRef.value
        : anomalyDetectionRef.value;
    };

    const renderTabLabel = (icon: string, label: string) => (
      <span class='ai-config-tab-label'>
        <i class={['icon-monitor', icon]} />
        <span>{label}</span>
      </span>
    );

    /**
     * @description 渲染离开页面的确认弹窗
     * InfoBox 默认只支持两个底部按钮，因此通过 footer 函数自定义三个操作：直接离开 / 保存并离开 / 取消
     */
    const showLeaveConfirm = (): Promise<boolean> => {
      return new Promise(resolve => {
        const box = InfoBox({
          title: t('确认离开当前页？'),
          subTitle: t('当前配置尚未保存，离开将会导致未保存信息丢失'),
          showMask: true,
          /**
           * 用户点击右上角关闭按钮 / 遮罩 / ESC 时视作「取消」，阻止离开
           * 这里仅作为兜底（不通过底部按钮也能关闭）
           */
          onClose: () => resolve(false),
          /**
           * 用 footer 自定义三个按钮，标题为「直接离开」，主按钮为「保存并离开」
           */
          footer: () => {
            const handleLeave = async () => {
              box.hide();
              resolve(true);
            };
            const handleSaveAndLeave = async () => {
              const child = getActiveChild();
              if (!child?.save) {
                box.hide();
                resolve(true);
                return;
              }
              // 保存成功才允许离开，失败则停留在原页面
              const success = await child.save();
              box.hide();
              resolve(!!success);
            };
            const handleCancel = () => {
              box.hide();
              resolve(false);
            };

            return (
              <div class='ai-config-leave-footer'>
                <Button
                  theme='primary'
                  onClick={handleLeave}
                >
                  {t('直接离开')}
                </Button>
                <Button
                  class='ai-config-leave-save-btn'
                  outline={true}
                  theme='primary'
                  onClick={handleSaveAndLeave}
                >
                  {t('保存并离开')}
                </Button>
                <Button onClick={handleCancel}>{t('取消')}</Button>
              </div>
            ) as any;
          },
        });
      });
    };

    /**
     * 离开页面钩子：若当前 Tab 组件表单被编辑过，弹出确认提示让用户决定下一步
     */
    onBeforeRouteLeave(async () => {
      const child = getActiveChild();
      if (!child?.isEdited) return true;
      return showLeaveConfirm();
    });

    return () => (
      <div class='ai-config'>
        <Tab
          class='ai-config-tab'
          active={activeTab.value}
          type='card-grid'
          onChange={handleTabChange}
        >
          <Tab.TabPanel
            v-slots={{ label: () => renderTabLabel('icon-yichangjiance', t('异常检测')) }}
            label={t('异常检测')}
            name={EAiConfigTab.anomalyDetection}
          >
            <AnomalyDetection ref='anomalyDetection' />
          </Tab.TabPanel>
          <Tab.TabPanel
            v-slots={{ label: () => renderTabLabel('icon-code', t('源码 AI 分析')) }}
            label={t('源码 AI 分析')}
            name={EAiConfigTab.sourceCodeAnalysis}
          >
            <SourceCodeAnalysis ref='sourceCodeAnalysis' />
          </Tab.TabPanel>
        </Tab>
      </div>
    );
  },
});
