import { useAuthStore } from '@/stores/authStore'

function getUserRoles(user: { roles?: string[]; role?: string } | null): string[] {
  if (!user) return []
  const roles: string[] = []
  if (Array.isArray(user.roles)) {
    roles.push(...user.roles.map(r => r.toUpperCase()))
  }
  if (typeof user.role === 'string' && user.role) {
    roles.push(user.role.toUpperCase())
  }
  return roles
}

export function usePermission() {
  const { user } = useAuthStore()
  const roles = getUserRoles(user)
  return {
    isAdmin: roles.includes('ADMIN'),
    isTrader: roles.includes('TRADER') || roles.includes('ADMIN'),
    isViewer: roles.includes('VIEWER') || roles.length === 0,
    can: (requiredRoles: string[]) => requiredRoles.some(r => roles.includes(r)),
    canWrite: roles.includes('TRADER') || roles.includes('ADMIN'),
    canManage: roles.includes('ADMIN'),
  }
}
