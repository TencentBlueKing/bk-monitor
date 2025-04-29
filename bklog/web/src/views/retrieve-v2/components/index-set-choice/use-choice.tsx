export default (props, { emit }) => {
  /**
   * 多选：选中操作
   * @param item
   * @param value
   */
  const handleIndexSetItemCheck = (item, value) => {
    const targetValue = [];

    // 如果是选中
    if (value) {
      props.value.forEach((v: any) => {
        targetValue.push(v);
      });
      targetValue.push(item.index_set_id);
      emit('value-change', targetValue);
      return;
    }

    // 如果是取消选中
    props.value.forEach((v: any) => {
      if (v !== item.index_set_id) {
        targetValue.push(v);
      }
    });

    emit('value-change', targetValue);
  };

  return {
    handleIndexSetItemCheck,
  };
};
