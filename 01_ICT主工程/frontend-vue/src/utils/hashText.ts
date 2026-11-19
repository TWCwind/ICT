// 稳定散列：同一个字符串永远得到同一个整数（用于按标签生成固定纹理/颜色）。
export function hashText(text: string) {
  let hash = 0
  for (let i = 0; i < text.length; i += 1) hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0
  return Math.abs(hash)
}
