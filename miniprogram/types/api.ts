export type EnvironmentKind = 'demo' | 'authorized' | 'unconfigured'

export type ApiErrorCode =
  | 'UNAUTHORIZED'
  | 'CONSENT_REQUIRED'
  | 'IDENTITY_REQUIRED'
  | 'ACCOUNT_STOPPED'
  | 'CONFLICT'
  | 'UNAVAILABLE'
  | 'VALIDATION_ERROR'
  | 'NETWORK_ERROR'
  | 'NOT_FOUND'

export interface ApiError {
  code: ApiErrorCode
  message: string
  retryable?: boolean
}

export interface ApiEnvelope<T> {
  request_id: string
  data: T | null
  error: ApiError | null
}

export interface StudentSession {
  accessToken: string
  expiresAt: string
  identityVerified: boolean
  basicConsent: boolean
  communityConsent: boolean
  accountStatus: 'active' | 'recovery'
}

export interface QuoteProjection {
  text: string
  attribution: string
  available: boolean
}

export interface MoodRecord {
  id: string
  mood: string
  recordedAt: string
}

export interface TodayProjection {
  quote: QuoteProjection
  mood: MoodRecord | null
  recentObservation: string | null
}

export interface AssessmentModule {
  key: 'phq9' | 'gad7' | 'sleep'
  title: string
  purpose: string
  duration: string
  questionCount: number
  lastCompletedAt: string | null
}

export interface AssessmentQuestion {
  id: string
  prompt: string
  options: string[]
}

export interface AssessmentSession {
  id: string
  module: AssessmentModule['key']
  title: string
  questionnaireVersion: string
  questions: AssessmentQuestion[]
}

export interface SleepDimension {
  name: string
  summary: string
}

export interface AssessmentResult {
  id: string
  module: AssessmentModule['key']
  title: string
  completedAt: string
  kind: 'ordinary' | 'higher_score' | 'safety_support' | 'insufficient_data'
  score: number | null
  interpretation: string
  nextStep: string
  sleepDimensions?: SleepDimension[]
  safetyState?: 'can_be_safe' | 'uncertain' | 'cannot_be_safe'
}

export interface SupportResource {
  id: string
  group: 'trusted_person' | 'campus' | 'emergency'
  title: string
  description: string
  phone?: string
  url?: string
  updatedAt: string
}

export type TreeholeStatus =
  | 'checking'
  | 'published'
  | 'protected'
  | 'pending_confirmation'
  | 'unpublished'
  | 'safety_priority'
  | 'deleted'

export interface TreeholeResponse {
  id: string
  displayName: string
  body: string
  createdAt: string
  status: 'checking' | 'published'
}

export interface TreeholePost {
  id: string
  displayName: string
  body: string | null
  excerpt: string | null
  status: TreeholeStatus
  createdAt: string
  responseCount: number
  responses?: TreeholeResponse[]
  mine: boolean
}

export interface UserProjection {
  displayName: string | null
  accountStatus: 'active' | 'recovery'
  recoveryUntil: string | null
  basicConsent: boolean
  communityConsent: boolean
  identityVerified: boolean
}

export interface HistoryItem {
  id: string
  category: 'mood' | 'assessment' | 'sleep'
  title: string
  summary: string
  recordedAt: string
  deletable: boolean
}
