export const ES_STORAGE_TABLE_KIND_OPTIONS = [
  { label: '实体表', value: 'physical' },
  { label: '虚拟表', value: 'virtual' }
];

export const ES_STORAGE_TABLE_KIND_LABEL: Record<'physical' | 'virtual', string> = {
  physical: '实体表',
  virtual: '虚拟表'
};

export const ES_STORAGE_TABLE_KIND_TONE: Record<'physical' | 'virtual', 'success' | 'warning'> = {
  physical: 'success',
  virtual: 'warning'
};
