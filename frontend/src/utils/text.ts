/**
 * 压缩连续空行：模型输出的思考过程（reasoning_content）常带 2~4 个连续换行，
 * pre-wrap 会原样保留，看起来段落间空白很大。这里压成最多一个空行（段落间距）。
 */
export function compactReasoning(text: string): string {
  return text
      .replace(/\r\n/g, '\n')
      .replace(/\n{2,}/g, '\n')   // 连续换行 → 单换行：段落之间不再留空行
      .trim()
}
