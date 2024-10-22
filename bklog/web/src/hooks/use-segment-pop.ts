import useLocale from '@/hooks/use-locale';
import Vue, { h, onMounted, ref, Ref } from 'vue';
import { debounce } from 'lodash';
import TaskRunning from '../global/utils/task-pool';

export default ({ onSegmentEnumClick }) => {
  const { $t } = useLocale();
  const className = 'bklog-segment-pop-content';
  const wrapperClassName = 'bklog-pop-wrapper';
  const wrapperIdName = 'bklog_pop_wrapper';
  const refContent = ref();

  const eventBoxList = [
    {
      onClick: () => onSegmentEnumClick('copy'),
      iconName: 'icon bklog-icon bklog-copy',
      text: $t('复制'),
    },
    {
      onClick: () => onSegmentEnumClick('is'),
      iconName: 'icon bk-icon icon-plus-circle',
      text: $t('添加到本次检索'),
      link: {
        tooltip: $t('新开标签页'),
        iconName: 'bklog-icon bklog-jump',
        onClick: e => {
          e.stopPropagation();
          onSegmentEnumClick('is', true);
        },
      },
    },
    {
      onClick: () => onSegmentEnumClick('not'),
      iconName: 'icon bk-icon icon-minus-circle',
      text: $t('从本次检索中排除'),
      link: {
        tooltip: $t('新开标签页'),
        iconName: 'bklog-icon bklog-jump',
        onClick: e => {
          e.stopPropagation();
          onSegmentEnumClick('not', true);
        },
      },
    },
    {
      onClick: () => onSegmentEnumClick('new-search-page-is', true),
      iconName: 'icon bk-icon icon-plus-circle',
      text: $t('新建检索'),
      link: {
        iconName: 'bklog-icon bklog-jump',
      },
    },
  ];

  const createSegmentContent = (refName: Ref) =>
    h('div', { class: 'event-icons', ref: refName }, [
      eventBoxList.map(item =>
        h(
          'div',
          {
            class: 'event-box',
          },
          [
            h('span', {
              class: 'event-btn',
              on: {
                click: item.onClick,
              },
            }),
            h('i', { class: item.iconName }),
            h('span', {}, [item.text]),
            item.link
              ? h(
                  'div',
                  {
                    class: 'new-link',
                    on: { ...(item.link.onClick ? { click: item.link.onClick } : {}) },
                    directives: item.link.tooltip
                      ? [
                          {
                            name: 'bk-tooltips',
                            value: item.link.tooltip,
                          },
                        ]
                      : [],
                  },
                  [h('i', { class: item.link.iconName })],
                )
              : null,
          ],
        ),
      ),
    ]);

    const PopComponent = {
      functional: true,
      render: () => {
        return h('div', { class: className }, [createSegmentContent(refContent)]);
      }
    };

  const mountedToBody = () => {
    let target = document.body.querySelector(`.${wrapperClassName}`);
    if (!target) {
      target = document.createElement('div');
      target.setAttribute('id', wrapperIdName);
      target.classList.add(wrapperClassName);
      document.body.appendChild(target);


      const app = new Vue({
        // components: { PopComponent },
        // template: '<PopComponent></PopComponent>'
        render: () => {
          return h('div', { class: className, style: 'display: none;' }, [createSegmentContent(refContent)]);
        }
      });
      const tempDiv = document.createElement('div');
      app.$mount(tempDiv);
      target.append(app.$el);
    }
  };

  const getSegmentContent = () => refContent;
  onMounted(() => {
    TaskRunning(mountedToBody);
  });

  return { getSegmentContent };
};
