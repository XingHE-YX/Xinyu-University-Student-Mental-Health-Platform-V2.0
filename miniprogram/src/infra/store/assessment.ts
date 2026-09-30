import type { AssessmentQuestion, AssessmentModule, AssessmentResult } from '../types/api'

export interface LocalAssessmentState {
  sessionId: string
  module: AssessmentModule['key']
  title: string
  questions: AssessmentQuestion[]
  answers: number[]
  currentIndex: number
  safetyState?: 'can_be_safe' | 'uncertain' | 'cannot_be_safe'
  result?: AssessmentResult
}

let state: LocalAssessmentState | null = null

export const assessmentStore = {
  start(next: Omit<LocalAssessmentState, 'answers' | 'currentIndex'>): LocalAssessmentState { state = { ...next, answers: [], currentIndex: 0 }; return state },
  get(): LocalAssessmentState | null { return state },
  setAnswer(index: number, value: number): void { if (!state) return; state.answers[index] = value; state.currentIndex = index },
  setSafety(value: LocalAssessmentState['safetyState']): void { if (state) state.safetyState = value },
  setResult(result: AssessmentResult): void { if (state) state.result = result },
  clear(): void { state = null },
}
