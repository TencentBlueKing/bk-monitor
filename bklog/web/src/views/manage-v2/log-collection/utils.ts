export const STATUS_ENUM = [
  {
    label: window.$t('部署中'),
    key: 'running',
    color: '#3A84FF',
    background: '#C5DBFF',
  },
  {
    label: window.$t('正常'),
    key: 'success',
    color: '#3FC06D',
    background: '#DAF6E5',
  },
  {
    label: window.$t('异常'),
    key: 'FAILED',
    color: '#EA3636',
    background: '#FFEBEB',
  },
  {
    label: window.$t('停用'),
    key: 'TERMINATED',
    color: '#979BA5',
    background: '#979ba529',
  },
];
