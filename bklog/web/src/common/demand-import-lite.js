/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/**
 * 轻量按需注册 bk-magic-vue 组件。
 *
 * 用于 hl=1 的独立详情页场景，避免每个新开详情 Tab 都加载完整 demand-import 组件集合。
 * 这里只注册采集详情首屏和其 Tab 内容实际会用到的基础组件/指令。
 */
import Vue from 'vue';

import {
  bkButton,
  bkDatePicker,
  bkException,
  bkLoading,
  bkOverflowTips,
  bkPopover,
  bkSideslider,
  bkTab,
  bkTabPanel,
  bkTable,
  bkTableColumn,
  bkTag,
  bkTooltips,
} from 'bk-magic-vue';

Vue.use(bkButton);
Vue.use(bkDatePicker);
Vue.use(bkException);
Vue.use(bkLoading);
Vue.use(bkOverflowTips);
Vue.use(bkPopover);
Vue.use(bkSideslider);
Vue.use(bkTab);
Vue.use(bkTabPanel);
Vue.use(bkTable);
Vue.use(bkTableColumn);
Vue.use(bkTag);
Vue.use(bkTooltips);
