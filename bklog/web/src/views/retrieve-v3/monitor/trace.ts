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
window.__IS_MONITOR_COMPONENT__ = true;
window.__IS_MONITOR_TRACE__ = true;
window.__IS_MONITOR_APM__ = false;
import Vue from 'vue';
import {
  bkBackTop,
  bkAffix,
  bkFixedNavbar,
  bkTransition,
  bkAlert,
  bkBadge,
  bkButton,
  bkAnimateNumber,
  bkCheckbox,
  bkCheckboxGroup,
  bkCollapse,
  bkCollapseItem,
  bkColorPicker,
  bkComposeFormItem,
  bkDatePicker,
  bkDialog,
  bkDiff,
  bkDropdownMenu,
  bkException,
  bkForm,
  bkFormItem,
  bkIcon,
  bkInput,
  bkOption,
  bkOptionGroup,
  bkPagination,
  bkPopover,
  bkPopconfirm,
  bkProcess,
  bkProgress,
  bkRadio,
  bkRadioButton,
  bkRadioGroup,
  bkRoundProgress,
  bkSelect,
  bkSideslider,
  bkSlider,
  bkSteps,
  bkSwitcher,
  bkTab,
  bkTabPanel,
  bkTable,
  bkTableColumn,
  bkTableSettingContent,
  bkTagInput,
  bkTimePicker,
  bkTimeline,
  bkTransfer,
  bkTree,
  bkUpload,
  bkContainer,
  bkCol,
  bkRow,
  bkNavigation,
  bkNavigationMenu,
  bkNavigationMenuItem,
  bkNavigationMenuGroup,
  bkSearchSelect,
  bkRate,
  bkStar,
  bkSwiper,
  bkVirtualScroll,
  bkZoomImage,
  bkBigTree,
  bkLink,
  bkCascade,
  bkVersionDetail,
  bkCard,
  bkImage,
  bkImageViewer,
  bkBreadcrumb,
  bkBreadcrumbItem,
  bkDivider,
  bkTag,
  bkResizeLayout,
  bkSpin,
  bkVirtualRender,
} from 'bk-magic-vue';

import i18n from '@/language/i18n';

if (!window.mainComponent?.$t) {
  window.mainComponent = {
    $t: i18n.t.bind(i18n),
    $i18n: i18n,
  };
}
import JsonFormatWrapper from '@/global/json-format-wrapper.vue';
import useStore from '@/hooks/use-store';

import MonitorTraceLog from './monitor';

const logStore = useStore();

const initMonitorState = (payload) => {
  logStore.commit('initMonitorState', payload);
};
const initGlobalComponents = () => {
  Vue.component('JsonFormatWrapper', JsonFormatWrapper);
  Vue.component('BkAffix', bkAffix);
  Vue.component('BkAlert', bkAlert);
  Vue.component('BkAnimateNumber', bkAnimateNumber);
  Vue.component('BkBackTop', bkBackTop);
  Vue.component('BkBadge', bkBadge);
  Vue.component('BkBigTree', bkBigTree);
  Vue.component('BkBreadcrumb', bkBreadcrumb);
  Vue.component('BkBreadcrumbItem', bkBreadcrumbItem);
  Vue.component('BkButton', bkButton);
  Vue.component('BkCard', bkCard);
  Vue.component('BkCascade', bkCascade);
  Vue.component('BkCheckbox', bkCheckbox);
  Vue.component('BkCheckboxGroup', bkCheckboxGroup);
  Vue.component('BkCol', bkCol);
  Vue.component('BkCollapse', bkCollapse);
  Vue.component('BkCollapseItem', bkCollapseItem);
  Vue.component('BkColorPicker', bkColorPicker);
  Vue.component('BkComposeFormItem', bkComposeFormItem);
  Vue.component('BkContainer', bkContainer);
  Vue.component('BkDatePicker', bkDatePicker);
  Vue.component('BkDialog', bkDialog);
  Vue.component('BkDiff', bkDiff);
  Vue.component('BkDivider', bkDivider);
  Vue.component('BkDropdownMenu', bkDropdownMenu);
  Vue.component('BkException', bkException);
  Vue.component('BkFixedNavbar', bkFixedNavbar);
  Vue.component('BkForm', bkForm);
  Vue.component('BkFormItem', bkFormItem);
  Vue.component('BkIcon', bkIcon);
  Vue.component('BkImage', bkImage);
  Vue.component('BkImageViewer', bkImageViewer);
  Vue.component('BkInput', bkInput);
  Vue.component('BkLink', bkLink);
  Vue.component('BkNavigation', bkNavigation);
  Vue.component('BkNavigationMenu', bkNavigationMenu);
  Vue.component('BkNavigationMenuGroup', bkNavigationMenuGroup);
  Vue.component('BkNavigationMenuItem', bkNavigationMenuItem);
  Vue.component('BkOption', bkOption);
  Vue.component('BkOptionGroup', bkOptionGroup);
  Vue.component('BkPagination', bkPagination);
  Vue.component('BkPopconfirm', bkPopconfirm);
  Vue.component('BkPopover', bkPopover);
  Vue.component('BkProcess', bkProcess);
  Vue.component('BkProgress', bkProgress);
  Vue.component('BkRadio', bkRadio);
  Vue.component('BkRadioButton', bkRadioButton);
  Vue.component('BkRadioGroup', bkRadioGroup);
  Vue.component('BkRate', bkRate);
  Vue.component('BkResizeLayout', bkResizeLayout);
  Vue.component('BkRoundProgress', bkRoundProgress);
  Vue.component('BkRow', bkRow);
  Vue.component('BkSearchSelect', bkSearchSelect);
  Vue.component('BkSelect', bkSelect);
  Vue.component('BkSideslider', bkSideslider);
  Vue.component('BkSlider', bkSlider);
  Vue.component('BkSpin', bkSpin);
  Vue.component('BkStar', bkStar);
  Vue.component('BkSteps', bkSteps);
  Vue.component('BkSwiper', bkSwiper);
  Vue.component('BkSwitcher', bkSwitcher);
  Vue.component('BkTab', bkTab);
  Vue.component('BkTabPanel', bkTabPanel);
  Vue.component('BkTable', bkTable);
  Vue.component('BkTableColumn', bkTableColumn);
  Vue.component('BkTableSettingContent', bkTableSettingContent);
  Vue.component('BkTag', bkTag);
  Vue.component('BkTagInput', bkTagInput);
  Vue.component('BkTimePicker', bkTimePicker);
  Vue.component('BkTimeline', bkTimeline);
  Vue.component('BkTransfer', bkTransfer);
  Vue.component('BkTransition', bkTransition);
  Vue.component('BkTree', bkTree);
  Vue.component('BkUpload', bkUpload);
  Vue.component('BkVersionDetail', bkVersionDetail);
  Vue.component('BkVirtualRender', bkVirtualRender);
  Vue.component('BkVirtualScroll', bkVirtualScroll);
  Vue.component('BkZoomImage', bkZoomImage);
};
const Vue2 = Vue;
export {
  MonitorTraceLog,
  logStore,
  i18n,
  Vue2,
  initMonitorState,
  initGlobalComponents,
};
