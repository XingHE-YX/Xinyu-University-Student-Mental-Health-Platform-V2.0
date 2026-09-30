import type { StudentSession, UserProjection } from '../types/api'

let session: StudentSession | null = null
let user: UserProjection = {
  displayName: null,
  accountStatus: 'active',
  recoveryUntil: null,
  basicConsent: false,
  communityConsent: false,
  identityVerified: false,
}
export const sessionStore = {
  get(): StudentSession | null {
    return session
  },
  set(next: StudentSession): void {
    session = next
  },
  clear(): void {
    session = null
    user = {
      displayName: null,
      accountStatus: 'active',
      recoveryUntil: null,
      basicConsent: false,
      communityConsent: false,
      identityVerified: false,
    }
  },
  getUser(): UserProjection {
    return user
  },
  setUser(next: UserProjection): void {
    user = next
  },
  accessToken(): string | undefined {
    return session?.accessToken
  },
}
