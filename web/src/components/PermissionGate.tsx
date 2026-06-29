import { ReactNode } from 'react'
import { usePermission } from '@/hooks/usePermission'

export interface PermissionGateProps {
  /** Required roles to access the children. User needs at least one of these roles. */
  requiredRoles: string[]
  /** Content to render when permission is denied. Default: null */
  fallback?: ReactNode
  /** Mode: 'hide' renders fallback (or null), 'disable' wraps children in disabled container */
  mode?: 'hide' | 'disable'
  /** Child nodes to render when permission is granted */
  children: ReactNode
}

/**
 * PermissionGate - A component that conditionally renders its children based on user roles.
 *
 * @example
 * ```tsx
 * // Hide content when denied
 * <PermissionGate requiredRoles={['TRADER', 'ADMIN']}>
 *   <Button>Execute Trade</Button>
 * </PermissionGate>
 *
 * // Show custom fallback when denied
 * <PermissionGate requiredRoles={['ADMIN']} fallback={<span>Admin only</span>}>
 *   <Settings />
 * </PermissionGate>
 *
 * // Disable instead of hide
 * <PermissionGate requiredRoles={['TRADER', 'ADMIN']} mode="disable">
 *   <Button>Submit Order</Button>
 * </PermissionGate>
 * ```
 */
export function PermissionGate({
  requiredRoles,
  fallback = null,
  mode = 'hide',
  children,
}: PermissionGateProps) {
  const { can } = usePermission()

  if (!can(requiredRoles)) {
    if (mode === 'hide') {
      return <>{fallback}</>
    }
    // mode === 'disable'
    return (
      <div
        style={{
          pointerEvents: 'none',
          opacity: 0.5,
          filter: 'grayscale(100%)',
        }}
      >
        {children}
      </div>
    )
  }

  return <>{children}</>
}

export default PermissionGate