import { ServicesInstance } from '@/platform/services';
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
import { bkLoadingDirective } from '../../platform/compat/tdesign/loading';
import SourceTranslation from '../../platform/i18n/translation';
import { patchLegacyComponentSlots } from '../../platform/compat/tdesign/legacy-slot';
import * as LegacyControls from 'bk-magic-vue';
import { patchLegacyFunctionalContext } from '../../platform/compat/tdesign/legacy-functional';
import { bkBigTree } from 'bk-magic-vue';
import { installHttp } from '@/platform/http';

export function configureApp(app: import('vue').App) {
  app.config.globalProperties.$services = ServicesInstance;
  patchLegacyFunctionalContext(bkBigTree);
  for (const component of Object.values(LegacyControls)) patchLegacyComponentSlots(component);
  // Vue.use may have registered a constructor cloned from the exported options.
  // Patch that actual column definition before mounting the application's tables.
  patchLegacyComponentSlots(app.component('bk-table-column'));
  app.component('i18n', SourceTranslation);
  app.directive('bkloading', bkLoadingDirective);
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
