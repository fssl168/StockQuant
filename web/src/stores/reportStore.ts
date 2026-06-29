import { create } from 'zustand'
import {
  reportApi,
  dailyReportApi,
  monthlyReportApi,
  annualReportApi,
  reportSearchApi,
  reportCrudApi,
  type Report,
  type ReportListParams,
} from '@/api/memory'

// ── 状态接口 ──────────────────────────────────────────────────

interface ReportState {
  // 数据
  dailyReports: Report[]
  monthlyReports: Report[]
  annualReports: Report[]
  currentReport: Report | null
  searchResults: Report[]
  searchQuery: string

  // 加载状态
  loadingDaily: boolean
  loadingMonthly: boolean
  loadingAnnual: boolean
  loadingCurrent: boolean
  loadingSearch: boolean
  generating: boolean

  // 错误状态
  error: string | null

  // 操作方法 -- 日报
  fetchDailyReports: (params?: ReportListParams) => Promise<void>
  fetchDailyReport: (date: string) => Promise<void>
  generateDailyReport: () => Promise<string | null>

  // 操作方法 -- 月报
  fetchMonthlyReports: (params?: ReportListParams) => Promise<void>
  fetchMonthlyReport: (yearMonth: string) => Promise<void>
  generateMonthlyReport: () => Promise<string | null>

  // 操作方法 -- 年报
  fetchAnnualReports: (params?: ReportListParams) => Promise<void>
  fetchAnnualReport: (year: string) => Promise<void>
  generateAnnualReport: () => Promise<string | null>

  // 操作方法 -- 统一检索
  searchReports: (query: string, reportType?: string) => Promise<void>
  clearSearch: () => void

  // 操作方法 -- CRUD
  addReport: (report: Record<string, unknown>) => Promise<string | null>
  deleteReport: (reportId: string) => Promise<boolean>

  // 操作方法 -- 清除
  clearCurrent: () => void
  clearError: () => void
}

export const useReportStore = create<ReportState>((set, get) => ({
  // ── 初始状态 ──

  dailyReports: [],
  monthlyReports: [],
  annualReports: [],
  currentReport: null,
  searchResults: [],
  searchQuery: '',

  loadingDaily: false,
  loadingMonthly: false,
  loadingAnnual: false,
  loadingCurrent: false,
  loadingSearch: false,
  generating: false,

  error: null,

  // ── 日报操作 ──

  fetchDailyReports: async (params) => {
    set({ loadingDaily: true, error: null })
    try {
      const reports = await dailyReportApi.list(params)
      set({ dailyReports: reports, loadingDaily: false })
    } catch (e) {
      set({ error: (e as Error).message, loadingDaily: false })
    }
  },

  fetchDailyReport: async (date) => {
    set({ loadingCurrent: true, error: null })
    try {
      const report = await dailyReportApi.get(date)
      set({ currentReport: report, loadingCurrent: false })
    } catch (e) {
      set({ error: (e as Error).message, loadingCurrent: false })
    }
  },

  generateDailyReport: async () => {
    set({ generating: true, error: null })
    try {
      const result = await dailyReportApi.generate()
      // 生成后刷新列表
      get().fetchDailyReports()
      set({ generating: false })
      return result.report
    } catch (e) {
      set({ error: (e as Error).message, generating: false })
      return null
    }
  },

  // ── 月报操作 ──

  fetchMonthlyReports: async (params) => {
    set({ loadingMonthly: true, error: null })
    try {
      const reports = await monthlyReportApi.list(params)
      set({ monthlyReports: reports, loadingMonthly: false })
    } catch (e) {
      set({ error: (e as Error).message, loadingMonthly: false })
    }
  },

  fetchMonthlyReport: async (yearMonth) => {
    set({ loadingCurrent: true, error: null })
    try {
      const report = await monthlyReportApi.get(yearMonth)
      set({ currentReport: report, loadingCurrent: false })
    } catch (e) {
      set({ error: (e as Error).message, loadingCurrent: false })
    }
  },

  generateMonthlyReport: async () => {
    set({ generating: true, error: null })
    try {
      const result = await monthlyReportApi.generate()
      get().fetchMonthlyReports()
      set({ generating: false })
      return result.report
    } catch (e) {
      set({ error: (e as Error).message, generating: false })
      return null
    }
  },

  // ── 年报操作 ──

  fetchAnnualReports: async (params) => {
    set({ loadingAnnual: true, error: null })
    try {
      const reports = await annualReportApi.list(params)
      set({ annualReports: reports, loadingAnnual: false })
    } catch (e) {
      set({ error: (e as Error).message, loadingAnnual: false })
    }
  },

  fetchAnnualReport: async (year) => {
    set({ loadingCurrent: true, error: null })
    try {
      const report = await annualReportApi.get(year)
      set({ currentReport: report, loadingCurrent: false })
    } catch (e) {
      set({ error: (e as Error).message, loadingCurrent: false })
    }
  },

  generateAnnualReport: async () => {
    set({ generating: true, error: null })
    try {
      const result = await annualReportApi.generate()
      get().fetchAnnualReports()
      set({ generating: false })
      return result.report
    } catch (e) {
      set({ error: (e as Error).message, generating: false })
      return null
    }
  },

  // ── 统一检索 ──

  searchReports: async (query, reportType) => {
    set({ loadingSearch: true, error: null, searchQuery: query })
    try {
      const results = await reportSearchApi.search({ query, reportType })
      set({ searchResults: results, loadingSearch: false })
    } catch (e) {
      set({ error: (e as Error).message, loadingSearch: false })
    }
  },

  clearSearch: () => {
    set({ searchResults: [], searchQuery: '' })
  },

  // ── CRUD ──

  addReport: async (report) => {
    set({ error: null })
    try {
      const result = await reportCrudApi.add(report)
      // 刷新对应类型的列表
      const type = report.report_type as 'daily' | 'monthly' | 'annual'
      if (type === 'daily') get().fetchDailyReports()
      else if (type === 'monthly') get().fetchMonthlyReports()
      else if (type === 'annual') get().fetchAnnualReports()
      return result.id
    } catch (e) {
      set({ error: (e as Error).message })
      return null
    }
  },

  deleteReport: async (reportId) => {
    set({ error: null })
    try {
      await reportCrudApi.delete(reportId)
      // 从所有列表中移除已删除的报告
      set((state) => ({
        dailyReports: state.dailyReports.filter((r) => r.id !== reportId),
        monthlyReports: state.monthlyReports.filter((r) => r.id !== reportId),
        annualReports: state.annualReports.filter((r) => r.id !== reportId),
        searchResults: state.searchResults.filter((r) => r.id !== reportId),
        currentReport: state.currentReport?.id === reportId ? null : state.currentReport,
      }))
      return true
    } catch (e) {
      set({ error: (e as Error).message })
      return false
    }
  },

  // ── 清除 ──

  clearCurrent: () => set({ currentReport: null }),
  clearError: () => set({ error: null }),
}))
