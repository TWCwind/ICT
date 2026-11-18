// 练习中心与练习页共用的 localStorage 键与读取逻辑。
// 抽出来的目的：让页面文件只留交互逻辑，键名只有一处定义。

export function activeQuestionBankStorageKey(id: string) {
  return `exercise_active_question_banks:${id || 'anonymous'}`
}

export function readActiveQuestionBankIds(id: string) {
  try {
    const raw = window.localStorage.getItem(activeQuestionBankStorageKey(id))
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : []
  } catch {
    return []
  }
}
