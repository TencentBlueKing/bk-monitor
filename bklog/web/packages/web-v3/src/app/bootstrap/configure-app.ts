import { ServicesInstance } from '@/platform/services';
import { Button, Checkbox, CheckboxGroup, Radio, RadioButton, RadioGroup, Switch, Loading, Alert, Tag, Progress, Badge, Input, LoadingPlugin, LoadingDirective } from 'tdesign-vue-next';
import 'tdesign-vue-next/es/loading/style/index.css';
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

export function configureApp(app: import('vue').App) {
  app.component('TButton', Button);
  app.component('TCheckbox', Checkbox);
  app.component('TCheckboxGroup', CheckboxGroup);
  app.component('TRadio', Radio);
  app.component('TRadioButton', RadioButton);
  app.component('TRadioGroup', RadioGroup);
  app.component('TSwitch', Switch);
  app.component('TLoading', Loading);
  app.component('TAlert', Alert);
  app.component('TTag', Tag);
  app.component('TProgress', Progress);
  app.component('TBadge', Badge);
  app.component('TInput', Input);
  app.config.globalProperties.$services = ServicesInstance;
  installLegacyBkControls(app);
  app.component('i18n', SourceTranslation);
  app.use(LoadingPlugin);
  app.directive('loading', LoadingDirective);
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
