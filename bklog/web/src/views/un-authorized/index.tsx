import { computed, defineComponent } from 'vue';
import useRoute from '@/hooks/use-route';


export default defineComponent({
  name: 'UnAuthorized',
  setup() {
    const route = useRoute();
    const exceptionMap = {
      space: '空间',
      indexset: '索引集',
      api: 'API',
    };

    const exceptionText = computed(() => {
      const type = route.query.type as keyof typeof exceptionMap;
      return exceptionMap[type as keyof typeof exceptionMap];
    });

    const handleApply = () => {
      console.log('handleApply');
    };

    const exceptionStyle = `height: calc(100vh - 100px); 
      display: flex; 
      flex-direction: column; 
      justify-content: center; 
      align-items: center;`;

    return () => <div>
      <bk-exception style={exceptionStyle} type='403' scene='part' >
        <div class='text-wrap text-part'>
          <span>{exceptionText.value} 无权限，请先申请</span>
          <span class='text-btn' onClick={handleApply}>去申请</span>
        </div>
      </bk-exception>
    </div>;
  },
});
