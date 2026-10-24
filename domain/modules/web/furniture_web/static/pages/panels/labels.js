export function formatMm(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const rounded = Math.round(number);
  if (Math.abs(number - rounded) < 1e-6) return String(rounded);
  return number.toFixed(1);
}

export function triple(values) {
  return values.map(formatMm).join(" × ");
}

export function panelCounts(panels) {
  const counts = {};
  for (const panel of panels) {
    counts[panel.assembly] = (counts[panel.assembly] || 0) + 1;
  }
  return counts;
}

// 页面上材料只有两种，图例也照这个来。
const MATERIAL_LABELS = { wood: "柜体木纹", white: "门板白色" };

export function materialLabel(material) {
  return MATERIAL_LABELS[material] || "柜体木纹";
}

// 顺纹方向：柜体坐标里的轴。规则与判据在板件阶段的 `grain_rules.py`。
// `y`（沿深）不在默认表里，但订单可以特意改成它——所以标签必须认全，不能漏。
const GRAIN_LABELS = { x: "沿宽", y: "沿深", z: "沿高", none: "不限" };

export function grainLabel(axis) {
  return GRAIN_LABELS[axis] || `未知(${axis})`;
}
