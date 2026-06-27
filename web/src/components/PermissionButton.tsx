import { Button, Tooltip, type ButtonProps } from 'antd'
import { usePermission } from '@/hooks/usePermission'

interface PermissionButtonProps extends ButtonProps {
  requiredRoles: string[]
  mode?: 'disable' | 'hide'
}

export function PermissionButton({ requiredRoles, mode = 'disable', children, ...props }: PermissionButtonProps) {
  const { can } = usePermission()
  if (!can(requiredRoles)) {
    if (mode === 'hide') return null
    return <Tooltip title="无权限"><Button {...props} disabled>{children}</Button></Tooltip>
  }
  return <Button {...props}>{children}</Button>
}
