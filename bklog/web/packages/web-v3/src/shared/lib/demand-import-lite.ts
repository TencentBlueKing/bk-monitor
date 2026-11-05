/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/**
 * 轻量按需注册 TDesign 组件。
 * 用于 hl=1 的独立详情页，避免加载完整组件集合。
 */
import Vue from 'vue';
import { Button, Drawer, Empty, Popup, TabPanel, Table, Tabs, Tag } from 'tdesign-vue-next';

for (const component of [Button, Drawer, Empty, Popup, TabPanel, Table, Tabs, Tag]) {
  Vue.use(component);
}
