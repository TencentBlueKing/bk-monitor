/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadScriptSetup } from './helpers/load-script-setup.mjs';

test('more menu initializes from hydrated Pinia state and hides for union queries',()=>{
  const state={isExternal:false,spaceUid:'fixture-space',indexId:'900101',retrieve:{flatIndexSetList:[{index_set_id:'900101',scenario_id:'log',collector_scenario_id:'container'}]},indexSetFieldConfig:{clustering_config:{is_active:false}},storeIsShowClusterStep:false,bkBizId:'900001'};
  for(const union of [false,true]){
    const component=loadScriptSetup(new URL('../src/features/retrieval/workbench/sub-bar/more-setting.vue',import.meta.url),{
      useRetrieveStore:()=>({$state:state.retrieve}),useStore:()=>({state,getters:{isUnionSearch:union,isShowMaskingTemplate:false}}),useRouter:()=>({}),useLocale:()=>({$t:x=>x}),isFeatureToggleOn:()=>false,
    });
    const model=component.setup({}, {expose:()=>{},emit:()=>{}});
    assert.equal(model.isShowRetrieveSetting.value,!union);
    assert.deepEqual(model.showSettingMenuList.value.map(item=>item.id),['logInfo']);
  }
});
