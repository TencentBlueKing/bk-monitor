import { computed, onMounted, ref } from 'vue';
import * as monaco from 'monaco-editor';
import { setDorisFields } from './lang';
import useStore from '@/hooks/use-store';

export default ({ refRootElement, sqlContent }) => {
  const editorInstance = ref();
  const store = useStore();
  const fieldList = computed(() => store.state.indexFieldInfo.fields);

  const initEditorInstance = () => {
    // 初始化编辑器
    editorInstance.value = monaco.editor.create(refRootElement.value, {
      value: sqlContent.value,
      language: 'dorisSQL',
      theme: 'vs-dark',
      padding: { top: 10, bottom: 10 },
    });

    // 监听编辑器的键盘事件
    editorInstance.value.onKeyDown(e => {
      if (e.keyCode === monaco.KeyCode.Space) {
        // 阻止默认空格行为，使得我们可以手动处理
        e.preventDefault();

        // 获取当前光标位置
        const position = editorInstance.value.getPosition();

        // 手动插入空格
        editorInstance.value.executeEdits(null, [
          {
            range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
            text: ' ',
            forceMoveMarkers: true,
          },
        ]);

        // 触发自动补全
        editorInstance.value.trigger('keyboard', 'editor.action.triggerSuggest', {});
      }
    });
  };

  const setSuggestFields = () => {
    setDorisFields(() =>
      fieldList.value.map(field => {
        return { name: field.field_name, type: field.field_type, description: field.description };
      }),
    );
  };

  onMounted(() => {
    setTimeout(() => {
      initEditorInstance();
      setSuggestFields();
    });
  });

  return {
    editorInstance,
  };
};
