import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, message, Space } from 'antd'
import { User, Lock } from '@phosphor-icons/react'
import { useAuthStore } from '@/stores/authStore'

const { Title, Text } = Typography

export default function Login() {
  const { login, loading } = useAuthStore()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [isRegister, setIsRegister] = useState(false)

  const handleSubmit = async (values: { username: string; password: string }) => {
    try {
      if (isRegister) {
        await (await import('@/api/client')).default.post('/api/auth/register', values)
        message.success('注册成功，请登录')
        setIsRegister(false)
      } else {
        await login(values.username, values.password)
        message.success('登录成功')
        navigate('/')
      }
    } catch (e: any) {
      message.error(e.message || (isRegister ? '注册失败' : '用户名或密码错误'))
    }
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh', background: '#09090b',
    }}>
      <Card
        style={{ width: 400, background: '#18181b', border: '1px solid #27272a', borderRadius: 12 }}
        styles={{ body: { padding: '32px 28px' } }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <Title level={3} style={{ color: '#f4f4f5', marginBottom: 4 }}>StockQuant</Title>
            <Text style={{ color: '#71717a' }}>AI 原生量化交易平台</Text>
          </div>

          <Form form={form} onFinish={handleSubmit} layout="vertical" size="large">
            <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
              <Input
                prefix={<User size={18} color="#71717a" />}
                placeholder="用户名"
                style={{ background: '#27272a', borderColor: '#3f3f46', color: '#f4f4f5' }}
              />
            </Form.Item>
            <Form.Item name="password" rules={[{ required: true, min: 6, message: '密码至少6位' }]}>
              <Input.Password
                prefix={<Lock size={18} color="#71717a" />}
                placeholder="密码"
                style={{ background: '#27272a', borderColor: '#3f3f46', color: '#f4f4f5' }}
              />
            </Form.Item>
            <Form.Item style={{ marginBottom: 12 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                style={{ height: 44, borderRadius: 8, fontWeight: 600 }}
              >
                {isRegister ? '注册' : '登录'}
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center' }}>
            <Text style={{ color: '#71717a' }}>
              {isRegister ? '已有账户？' : '没有账户？'}
              <Button
                type="link"
                onClick={() => setIsRegister(!isRegister)}
                style={{ color: '#3b82f6', padding: 0, height: 'auto', fontWeight: 500 }}
              >
                {isRegister ? '登录' : '注册'}
              </Button>
            </Text>
          </div>

          {!isRegister && (
            <div style={{ textAlign: 'center', padding: '8px 0', background: '#27272a', borderRadius: 6 }}>
              <Text style={{ color: '#52525b', fontSize: 12 }}>默认账户: admin / admin123</Text>
            </div>
          )}

          {!isRegister && (
            <div style={{ marginTop: 16 }}>
              <Text style={{ color: '#71717a', fontSize: 12, display: 'block', marginBottom: 8 }}>演示账号快捷登录</Text>
              <Space direction="vertical" style={{ width: '100%' }} size={6}>
                <Button
                  size="small"
                  onClick={() => { form.setFieldsValue({ username: 'admin', password: 'admin123' }); handleSubmit({ username: 'admin', password: 'admin123' }) }}
                  style={{ width: '100%', justifyContent: 'flex-start', fontSize: 11 }}
                >
                  管理员 admin / admin123
                </Button>
                <Button
                  size="small"
                  onClick={() => { form.setFieldsValue({ username: 'trader', password: 'trader123' }); handleSubmit({ username: 'trader', password: 'trader123' }) }}
                  style={{ width: '100%', justifyContent: 'flex-start', fontSize: 11 }}
                >
                  交易员 trader / trader123
                </Button>
                <Button
                  size="small"
                  onClick={() => { form.setFieldsValue({ username: 'viewer', password: 'viewer123' }); handleSubmit({ username: 'viewer', password: 'viewer123' }) }}
                  style={{ width: '100%', justifyContent: 'flex-start', fontSize: 11 }}
                >
                  观察者 viewer / viewer123
                </Button>
              </Space>
            </div>
          )}
        </Space>
      </Card>
    </div>
  )
}
