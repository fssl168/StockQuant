import { useEffect, useState } from 'react'
import { Table, Button, Modal, Form, Input, Select, Switch, Popconfirm, Space, Typography, message } from 'antd'
import { UserPlus, User, Key } from '@phosphor-icons/react'
import { useUserStore, type User as UserType } from '@/stores/userStore'
import { RoleBadge } from '@/components/RoleBadge'

const { Title, Text } = Typography
const ROLE_OPTIONS = [
  { value: 'ADMIN', label: '管理员' },
  { value: 'TRADER', label: '交易员' },
  { value: 'VIEWER', label: '观察者' },
]

export default function UserManagement() {
  const { users, loading, fetchUsers, createUser, updateUser, resetPassword, toggleDisable, deleteUser } = useUserStore()
  const [createModal, setCreateModal] = useState(false)
  const [editModal, setEditModal] = useState(false)
  const [resetModal, setResetModal] = useState(false)
  const [currentUser, setCurrentUser] = useState<UserType | null>(null)
  const [editForm] = Form.useForm()
  const [resetForm] = Form.useForm()
  const [createForm] = Form.useForm()

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const handleCreate = async (values: { username: string; password: string; roles: string[] }) => {
    try {
      await createUser(values)
      setCreateModal(false)
      createForm.resetFields()
      message.success('用户创建成功')
    } catch (e: any) {
      message.error(e.message || '创建用户失败')
    }
  }

  const handleEdit = async (values: { roles: string[] }) => {
    if (!currentUser) return
    try {
      await updateUser(currentUser.id, { roles: values.roles })
      setEditModal(false)
      setCurrentUser(null)
      message.success('用户信息更新成功')
    } catch (e: any) {
      message.error(e.message || '更新用户失败')
    }
  }

  const handleResetPassword = async (values: { password: string }) => {
    if (!currentUser) return
    try {
      await resetPassword(currentUser.id, values.password)
      setResetModal(false)
      setCurrentUser(null)
      resetForm.resetFields()
      message.success('密码重置成功')
    } catch (e: any) {
      message.error(e.message || '密码重置失败')
    }
  }

  const handleToggleDisable = async (userId: string) => {
    try {
      await toggleDisable(userId)
      message.success('操作成功')
    } catch (e: any) {
      message.error(e.message || '操作失败')
    }
  }

  const handleDelete = async (userId: string) => {
    try {
      await deleteUser(userId)
      message.success('用户已删除')
    } catch (e: any) {
      message.error(e.message || '删除用户失败')
    }
  }

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 150,
      render: (name: string) => <strong>{name}</strong>,
    },
    {
      title: '角色',
      dataIndex: 'roles',
      key: 'roles',
      width: 150,
      render: (roles: string[]) => (
        <Space size={4}>
          {roles.map(r => (
            <RoleBadge key={r} role={r} size="small" />
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'disabled',
      key: 'disabled',
      width: 80,
      render: (disabled: boolean, record: UserType) => (
        <Switch
          size="small"
          checked={!disabled}
          onChange={() => handleToggleDisable(record.id)}
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '—',
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: UserType) => (
        <Space size={4}>
          <Button size="small" onClick={() => { setCurrentUser(record); editForm.setFieldsValue({ roles: record.roles }); setEditModal(true) }}>编辑角色</Button>
          <Button size="small" onClick={() => { setCurrentUser(record); resetForm.resetFields(); setResetModal(true) }}>重置密码</Button>
          <Popconfirm title="确定删除此用户？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexShrink: 0 }}>
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>用户管理</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>管理系统用户账号和权限</Text>
        </div>
        <Button icon={<UserPlus size={16} />} onClick={() => { createForm.resetFields(); setCreateModal(true) }}>
          新建用户
        </Button>
      </div>

      <Table
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 个用户` }}
        style={{ flex: 1, overflow: 'auto' }}
      />

      {/* 新建用户 Modal */}
      <Modal title="新建用户" open={createModal} onCancel={() => setCreateModal(false)} footer={null} width={420}>
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<User size={16} />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6, message: '密码至少6位' }]}>
            <Input.Password placeholder="密码" />
          </Form.Item>
          <Form.Item name="roles" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select placeholder="选择角色" options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setCreateModal(false)}>取消</Button>
              <Button type="primary" htmlType="submit">创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑角色 Modal */}
      <Modal title="编辑用户角色" open={editModal} onCancel={() => { setEditModal(false); setCurrentUser(null) }} footer={null} width={420}>
        {currentUser && (
          <div style={{ marginBottom: 16 }}>
            <Text>用户名：<strong>{currentUser.username}</strong></Text>
          </div>
        )}
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          <Form.Item name="roles" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select mode="multiple" placeholder="选择角色" options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => { setEditModal(false); setCurrentUser(null) }}>取消</Button>
              <Button type="primary" htmlType="submit">保存</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 重置密码 Modal */}
      <Modal title="重置密码" open={resetModal} onCancel={() => { setResetModal(false); setCurrentUser(null) }} footer={null} width={420}>
        {currentUser && (
          <div style={{ marginBottom: 16 }}>
            <Text>用户名：<strong>{currentUser.username}</strong></Text>
          </div>
        )}
        <Form form={resetForm} layout="vertical" onFinish={handleResetPassword}>
          <Form.Item name="password" label="新密码" rules={[{ required: true, min: 6, message: '密码至少6位' }]}>
            <Input.Password prefix={<Key size={16} />} placeholder="新密码" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => { setResetModal(false); setCurrentUser(null) }}>取消</Button>
              <Button type="primary" htmlType="submit">重置</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
