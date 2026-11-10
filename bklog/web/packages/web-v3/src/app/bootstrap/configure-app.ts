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

import { ServicesInstance } from '@/platform/services';
import { Button, Checkbox, CheckboxGroup, Radio, RadioButton, RadioGroup, Switch, Loading, Alert, Tag, Progress, Badge, Input, Dialog, LoadingPlugin, LoadingDirective } from 'tdesign-vue-next';
import 'tdesign-vue-next/es/loading/style/index.css';

import VueVirtualScroller from 'vue-virtual-scroller';
import LogButton from '@/shared/ui/log-button/index.vue';
import LogIcon from '@/shared/ui/log-icon/index';
import { useDocLinks } from '@/shared/composables/use-doc-links';
import { renderHeader, xssFilter } from '../../shared/lib/util';
import JsonFormatWrapper from '../../shared/global/json-format-wrapper.vue';
import methods from '../../platform/plugins/methods';
import SourceTranslation from '../../platform/i18n/translation';
import { installLegacyBkControls } from '../../platform/compat/tdesign/legacy-bk-controls';
import { installHttp } from '@/platform/http';
import { bkInfoBox } from '@/platform/compat/tdesign/info-box';
import { messageError, messageInfo, messageSuccess, messageWarn } from '@/shared/lib/message';

const registerComponent = (app: import('vue').App, name: string, component: import('vue').Component) => {
  if (!app.component(name)) app.component(name, component);
};

export function configureApp(app: import('vue').App) {
  // 运行时模板沿用现有空白保留策略，避免 CONFIG_WHITESPACE 在每次编译时告警。
  app.config.compilerOptions.whitespace = 'preserve';
  registerComponent(app, 'TButton', Button);
  registerComponent(app, 'TCheckbox', Checkbox);
  registerComponent(app, 'TCheckboxGroup', CheckboxGroup);
  registerComponent(app, 'TRadio', Radio);
  registerComponent(app, 'TRadioButton', RadioButton);
  registerComponent(app, 'TRadioGroup', RadioGroup);
  registerComponent(app, 'TSwitch', Switch);
  registerComponent(app, 'TLoading', Loading);
  registerComponent(app, 'TAlert', Alert);
  registerComponent(app, 'TTag', Tag);
  registerComponent(app, 'TProgress', Progress);
  registerComponent(app, 'TBadge', Badge);
  registerComponent(app, 'TInput', Input);
  registerComponent(app, 'TDialog', Dialog);
  app.config.globalProperties.$services = ServicesInstance;
  installLegacyBkControls(app);
  app.component('i18n', SourceTranslation);
  app.use(LoadingPlugin);
  if (!app.directive('loading')) app.directive('loading', LoadingDirective);
  app.config.globalProperties.$bkInfo = bkInfoBox;
  app.config.globalProperties.messageError = messageError;
  app.config.globalProperties.messageSuccess = messageSuccess;
  app.config.globalProperties.messageInfo = messageInfo;
  app.config.globalProperties.messageWarn = messageWarn;
  app.config.globalProperties.$renderHeader = renderHeader;
  app.config.globalProperties.$xss = xssFilter;
  app.component('JsonFormatWrapper', JsonFormatWrapper);
  app.component('LogButton', LogButton);
  app.component('LogIcon', LogIcon);
  app.config.globalProperties.handleGotoLink = useDocLinks().handleGotoLink;
  app.use(methods);
  app.use(VueVirtualScroller);
  installHttp(app);
}
