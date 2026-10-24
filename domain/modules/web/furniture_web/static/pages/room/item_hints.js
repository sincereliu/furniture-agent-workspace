export function fillsWall(item){return !!(item&&item.placement&&item.placement.fill)}
export function selectHint(item,READ_ONLY){
  if(READ_ONLY)return `已选中 ${item.label}`;
  if(fillsWall(item))return `已选中 ${item.label}：铺满这面墙，可改离地高度`;
  return item.placement.mode==="wall"
    ?`已选中 ${item.label}：靠墙贴合，向外拖可离开墙面`
    :`已选中 ${item.label}：拖动可移动`;
}
