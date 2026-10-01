/** Convert canonical placed items to the canvas model once, at the page boundary. */
export function normalizeItems(items) {
  return items.map((item) => ({
    ...item,
    placement: { ...item.placement },
    z_start: item.placement.origin_z_mm,
    z_end: item.placement.origin_z_mm + item.height,
    footprint: item.footprint.map(({ x_mm, y_mm }) => [x_mm, y_mm]),
  }));
}
