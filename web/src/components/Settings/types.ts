// Settings 页面类型定义

export interface SettingEntry {
  key: string
  value: unknown
  defaultValue: unknown
  valueType: 'string' | 'number' | 'boolean' | 'select' | 'password' | 'float'
  label: string
  description?: string
  secret?: boolean
  min?: number
  max?: number
  step?: number
  scale?: number
  unit?: string
  slider?: boolean
  options?: { value: string; label: string }[]
  when?: {
    field: string
    values: string[]
  }
}

export interface GroupEntry {
  key: string
  label: string
  icon: string
  iconComponent?: React.ReactNode
  items: SettingEntry[]
}
