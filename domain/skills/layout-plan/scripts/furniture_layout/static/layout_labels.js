// 屏幕标注排布：保留上次偏移，避让文字矩形，限制在画布内。
export function placeLabels(labels, width, height) {
  const placed = [];
  const gap = 5, margin = 5;
  return labels.map((label) => {
    const step = label.height + gap;
    const offsets = [label.offset || [0, 0], [0, 0]];
    for (let row = 1; row <= 8; row += 1) {
      offsets.push([0, -row * step], [0, row * step]);
    }
    for (const side of [-1, 1]) {
      for (let row = -4; row <= 4; row += 1) {
        offsets.push([side * (label.width + gap), row * step]);
      }
    }
    const rectAt = ([dx, dy]) => {
      const x = Math.max(margin + label.width / 2,
        Math.min(width - margin - label.width / 2, label.x + dx));
      const y = Math.max(margin + label.height / 2,
        Math.min(height - margin - label.height / 2, label.y + dy));
      return { x, y, width: label.width, height: label.height,
        offset: [x - label.x, y - label.y] };
    };
    const overlaps = (rect) => placed.some((other) =>
      Math.abs(rect.x - other.x) < (rect.width + other.width) / 2 + gap &&
      Math.abs(rect.y - other.y) < (rect.height + other.height) / 2 + gap);
    const rect = offsets.map(rectAt).find((candidate) => !overlaps(candidate)) || rectAt([0, 0]);
    placed.push(rect);
    return rect;
  });
}
