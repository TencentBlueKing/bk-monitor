import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const root = new URL('../src/features/retrieval/workspace/favorite/', import.meta.url);
const native = Object.fromEntries(
  ['Button', 'Form', 'FormItem', 'Input', 'Select', 'Option', 'Textarea', 'Dialog', 'Loading'].map((name) => [
    name,
    { name },
  ]),
);
const compiler = { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' };
function find(node, type) {
  if (!node) return;
  if (Array.isArray(node)) {
    for (const item of node) {
      const value = find(item, type);
      if (value) return value;
    }
    return;
  }
  if (node.type === type) return node;
  return find(node.children, type);
}
function setup(file, props, options = {}) {
  const calls = [],
    events = [];
  const store = {
    state: {
      spaceUid: 'bkcc__5000140',
      indexItem: { keyword: 'current query', display_fields: ['log'], table_id_conditions: ['unconverted'] },
    },
    getters: {
      isSceneMode: !!options.scene,
      retrieveParams: {
        table_id_conditions: [[{ field_name: 'host', value: ['test'], op: '=' }]],
        scene_filter_values: [{ field: 'path', value: ['/log'], operator: '=' }],
      },
      'retrieve/sceneConfigList': [{ type: 'k8s', label: 'Kubernetes' }],
    },
  };
  const hook = {
    updateGroupName: async (params, spaceUid, isCreate, cb) => {
      calls.push({ method: 'group', params, spaceUid, isCreate });
      cb({ id: 77 });
    },
    getFavoriteData: async (id, target) => {
      calls.push({ method: 'load', id });
      Object.assign(target, {
        id,
        name: 'Saved',
        display_fields: ['saved-field'],
        visible_type: options.visibility ?? 'private',
        group_id: 2,
        keyword: 'saved query',
        source_type: options.scene ? 'scene' : 'index_set',
        scene_id: 'k8s',
        index_set_name: 'Sample index',
        index_set_names: ['A', 'B'],
        query_string: 'level:ERROR',
        params: { addition: [] },
      });
    },
    requestGroupList: async (spaceUid, cb) => {
      calls.push({ method: 'groups', spaceUid });
      cb({
        data: [
          { id: 1, name: 'Backend private', group_type: 'private' },
          { id: 2, name: 'Team', group_type: 'public' },
        ],
      });
    },
    handleUpdateFavorite: (value, cb) => {
      calls.push({ method: 'update', value: JSON.parse(JSON.stringify(value)) });
      cb(value);
    },
  };
  const mod = loadTypeScript(
    new URL('components/collect-list/' + file, root),
    {
      vue: Vue,
      'tdesign-vue-next': native,
      '@/shared/utils/typed-record': { asDictionary: (x) => x },
      '@/shared/composables/use-locale': () => ({ t: (x) => x }),
      '@/shared/composables/use-store': () => store,
      '../../hooks/use-favorite': { useFavorite: () => hook },
      '../../utils/index': {
        getGroupNameRules: () => ({}),
        handleApiError: (...args) => calls.push({ method: 'error', args }),
      },
      './add-group': { name: 'AddGroupFixture' },
      './add-group.scss': {},
      './edit-dialog.scss': {},
    },
    compiler,
  );
  const scope = Vue.effectScope();
  const render = scope.run(() => mod.default.setup(Vue.reactive(props), { emit: (...args) => events.push(args) }));
  return { render, calls, events, store, stop: () => scope.stop() };
}
test('sidebar group and favorite editor render native controls without legacy command services', () => {
  for (const file of ['add-group.tsx', 'edit-dialog.tsx']) {
    const src = readFileSync(new URL('components/collect-list/' + file, root), 'utf8');
    assert.doesNotMatch(src, /<\/?bk-(form|form-item|dialog|select|option|input)\b|v-bkloading|clearError/);
  }
  assert.doesNotMatch(readFileSync(new URL('utils/index.ts', root), 'utf8'), /\$bkMessage/);
});
test('inline group creation validates before original create/update operation', async () => {
  for (const isCreate of [false, true]) {
    const c = setup('add-group.tsx', {
      rules: {},
      isFormType: true,
      isCreate,
      data: { group_name: 'Original', group_id: 2 },
    });
    try {
      let vnode = c.render(),
        form = find(vnode, native.Form);
      form.ref.r.value = { validate: async () => ({ group_name: [{ result: false }] }), clearValidate() {} };
      find(vnode, native.Input).props.onChange('New group');
      await find(vnode, native.Button).props.onClick();
      assert.equal(c.calls.length, 0);
      form.ref.r.value.validate = async () => true;
      await find(c.render(), native.Button).props.onClick();
      assert.deepEqual(c.calls[0], {
        method: 'group',
        params: isCreate ? { group_new_name: 'New group' } : { group_new_name: 'New group', group_id: 2 },
        spaceUid: 'bkcc__5000140',
        isCreate,
      });
      assert.deepEqual(c.events, [['submit', 77, 'New group']]);
    } finally {
      c.stop();
    }
  }
});
test('inline group cancel clears validation and restores the original name for rename', () => {
  const c = setup('add-group.tsx', {
    rules: {},
    isFormType: true,
    isCreate: false,
    data: { group_name: 'Original', group_id: 2 },
  });
  try {
    const vnode = c.render();
    let cleared = 0;
    find(vnode, native.Form).ref.r.value = {
      clearValidate() {
        cleared++;
      },
    };
    find(vnode, native.Input).props.onChange('Draft');
    const buttons = vnode.children[1].children;
    buttons[1].props.onClick();
    assert.equal(find(c.render(), native.Input).props.value, 'Original');
    assert.equal(cleared, 1);
    assert.equal(c.calls.length, 0);
    assert.equal(c.events[0][0], 'cancel');
  } finally {
    c.stop();
  }
});
test('favorite editor loads original data and localized groups only when opened', async () => {
  const c = setup('edit-dialog.tsx', {
    isShow: true,
    data: { id: 5, index_set_type: 'union' },
    activeFavoriteID: 9,
    favoriteList: [],
  });
  try {
    assert.equal(c.calls.length, 0);
    await c.render().props.onOpened();
    assert.deepEqual(
      c.calls.map((x) => x.method),
      ['load', 'groups'],
    );
    const vnode = c.render(),
      form = find(vnode, native.Form);
    assert.equal(form.props.data.name, 'Saved');
    assert.equal(find(vnode, native.Select).props.options[0].label, '个人收藏');
    const texts = form.children[2];
    assert.equal(find(texts, native.Input).props.value, 'A,B');
    assert.equal(find(vnode, native.Textarea).props.disabled, true);
  } finally {
    c.stop();
  }
});
test('favorite editor blocks invalid saves and preserves saved settings for inactive favorite', async () => {
  const c = setup('edit-dialog.tsx', { isShow: true, data: { id: 5 }, activeFavoriteID: 9, favoriteList: [] });
  try {
    await c.render().props.onOpened();
    const form = find(c.render(), native.Form);
    form.ref.r.value = { validate: async () => ({ name: [{}] }) };
    await c.render().props.onConfirm();
    assert.equal(c.calls.filter((x) => x.method === 'update').length, 0);
    form.ref.r.value.validate = async () => true;
    await c.render().props.onConfirm();
    const update = c.calls.find((x) => x.method === 'update').value;
    assert.equal(update.keyword, 'saved query');
    assert.deepEqual(update.display_fields, ['saved-field']);
    assert.deepEqual(
      c.events.map((x) => x[0]),
      ['refresh-group', 'cancel'],
    );
  } finally {
    c.stop();
  }
});
test('active scene favorite preserves converted scene conditions over current index state', async () => {
  const c = setup(
    'edit-dialog.tsx',
    { isShow: true, data: { id: 5 }, activeFavoriteID: 5, favoriteList: [] },
    { scene: true, visibility: 'public' },
  );
  try {
    await c.render().props.onOpened();
    const vnode = c.render();
    assert.equal(find(vnode, native.Select).props.options.length, 1);
    find(vnode, native.Form).ref.r.value = { validate: async () => true };
    await vnode.props.onConfirm();
    const update = c.calls.find((x) => x.method === 'update').value;
    assert.equal(update.keyword, 'current query');
    assert.deepEqual(update.table_id_conditions, c.store.getters.retrieveParams.table_id_conditions);
    assert.deepEqual(update.scene_filter_values, c.store.getters.retrieveParams.scene_filter_values);
    assert.equal(find(vnode.children[0].children[0].children[2], native.Input).props.value, 'Kubernetes');
  } finally {
    c.stop();
  }
});
test('favorite feedback uses native MessagePlugin and retains original error text', () => {
  const messages = [];
  const mod = loadTypeScript(new URL('utils/index.ts', root), {
    'tdesign-vue-next': { MessagePlugin: (...args) => messages.push(args) },
  });
  mod.showMessage('Done');
  mod.handleApiError({ message: 'Backend failed' }, 'Fallback');
  assert.deepEqual(messages, [
    ['success', { content: 'Done' }],
    ['error', { content: 'Backend failed' }],
  ]);
});

test('user display SDK stays a real Custom Element in SFC and JSX compilation', async () => {
  const {createRequire}=await import('node:module');
  const require=createRequire(import.meta.url);
  const pluginRequire=createRequire(require.resolve('@vitejs/plugin-vue-jsx'));
  const babel=pluginRequire('@babel/core');
  const jsx=pluginRequire('@vue/babel-plugin-jsx');
  const isCustomElement=tag=>tag==='bk-user-display-name';
  const output=babel.transformSync('const node = <bk-user-display-name user-id="tester" />', {configFile:false,babelrc:false,plugins:[[jsx,{isCustomElement}]]}).code;
  assert.doesNotMatch(output,/resolveComponent/);
  assert.match(output,/"bk-user-display-name"/);
  const {compileTemplate}=require('@vue/compiler-sfc');
  const template=compileTemplate({source:'<bk-user-display-name user-id="tester" />',filename:'user.vue',id:'user',compilerOptions:{isCustomElement}});
  assert.deepEqual(template.errors,[]);
  assert.doesNotMatch(template.code,/resolveComponent/);
  const config=readFileSync(new URL('../vite.application.config.mjs',import.meta.url),'utf8');
  assert.equal((config.match(/isCustomElement: tag => tag === 'bk-user-display-name'/g)||[]).length,2);
});

test('group rename opens its popover without entering destructive confirmation; dismiss retains confirmation',()=>{
  const previous=globalThis.window, previousDocument=globalThis.document;globalThis.window={__IS_MONITOR_APM__:false};globalThis.document={body:{}};
  const Popover={name:'PopoverFixture'},Edit={name:'EditFixture'},Add={name:'AddFixture'};
  const scope=Vue.effectScope();
  try{
    const component=loadTypeScript(new URL('components/collect-list/collect-list.tsx',root),{
      vue:Vue,'tdesign-vue-next':native,'@/shared/utils/typed-record':{asDictionary:x=>x},
      '@/shared/ui/bklog-popover/index':Popover,'@/shared/global/overlay/index':{useDialogVisible:()=>{const visible=Vue.ref(false);return{visible,setVisible:value=>(visible.value=value),onValueChange:value=>(visible.value=value)}}},
      '@/shared/composables/use-locale':()=>({t:x=>x}),'@/shared/composables/use-store':()=>({state:{userMeta:{username:'tester'}}}),
      '../../../../../../shared/lib/util':{utcFormatDate:()=>''},'../../hooks/use-favorite':{useFavorite:()=>({})},
      '../../utils/index':{getGroupNameRules:()=>({})},'./add-group':Add,'./edit-dialog':Edit,'./collect-list.scss':{},
      './collect-list-menu-hover':{createFavoriteMenuHoverState:()=>({getOpenId:()=>null,shown(){},hidden(){},dispose(){},delay:1})},
    },compiler).default;
    const render=scope.run(()=>component.setup({list:[{group_id:77,group_name:'Owned group',group_type:'public',favorites:[]}],loading:false,isCollapse:true,isSearch:false},{emit(){}}));
    const menu=find(render(),Popover).props['v-slots'].content();
    const rename=menu.children[0];rename.children[0].props.onClick();
    assert.doesNotThrow(()=>render());assert.equal(find(render(),native.Dialog).props.visible,false);
    const renameForm=rename.props['v-slots'].content();assert.equal(find(renameForm,Add).props.isCreate,false);
    menu.children[1].props.onClick();const dialog=find(render(),native.Dialog);
    assert.equal(dialog.props.visible,true);assert.ok(JSON.stringify(dialog.children).includes('确认解散该分组'));
    dialog.props.onClose();assert.equal(find(render(),native.Dialog).props.visible,false);
  }finally{scope.stop();if(previous===undefined)delete globalThis.window;else globalThis.window=previous;if(previousDocument===undefined)delete globalThis.document;else globalThis.document=previousDocument}
});
