import client from "./client"

// ── 报告类型 ──────────────────────────────────────────────────

export interface Report {
  id: string
  userId: string
  reportType: "daily" | "monthly" | "annual"
  reportDate: string
  reportPeriodStart: string | null
  reportPeriodEnd: string | null
  marketReview: string
  tradingRecord: string
  strategyPerformance: string
  aiInsights: string
  fullContent: string
  summary: string
  confidence: number
  importanceScore: number
  metrics: Record<string, unknown>
  metadata: Record<string, unknown>
  createdAt: string
  lastAccessedAt: string | null
}

export interface ReportListParams {
  start?: string
  end?: string
  limit?: number
}

export interface SearchReportsParams {
  query: string
  reportType?: string
}

// ── 日报 API ─────────────────────────────────────────────────

export const dailyReportApi = {
  /** 获取日报列表 */
  list: (params?: ReportListParams) =>
    client.get("/api/reports/daily", { params }) as Promise<Report[]>,

  /** 获取指定日期的日报 */
  get: (date: string) =>
    client.get(`/api/reports/daily/${date}`) as Promise<Report>,

  /** AI 生成日报 */
  generate: () =>
    client.post("/api/reports/daily/generate") as Promise<{ success: boolean; report: string }>,
}

// ── 月报 API ─────────────────────────────────────────────────

export const monthlyReportApi = {
  /** 获取月报列表 */
  list: (params?: ReportListParams) =>
    client.get("/api/reports/monthly", { params }) as Promise<Report[]>,

  /** 获取指定年月的月报 */
  get: (yearMonth: string) =>
    client.get(`/api/reports/monthly/${yearMonth}`) as Promise<Report>,

  /** AI 生成月报 */
  generate: () =>
    client.post("/api/reports/monthly/generate") as Promise<{ success: boolean; report: string }>,
}

// ── 年报 API ─────────────────────────────────────────────────

export const annualReportApi = {
  /** 获取年报列表 */
  list: (params?: ReportListParams) =>
    client.get("/api/reports/annual", { params }) as Promise<Report[]>,

  /** 获取指定年份的年报 */
  get: (year: string) =>
    client.get(`/api/reports/annual/${year}`) as Promise<Report>,

  /** AI 生成年报 */
  generate: () =>
    client.post("/api/reports/annual/generate") as Promise<{ success: boolean; report: string }>,
}

// ── 统一检索 ─────────────────────────────────────────────────

export const reportSearchApi = {
  /** 检索报告 */
  search: (params: SearchReportsParams) =>
    client.post("/api/reports/search", {
      keyword: params.query,
      type: params.reportType || "all",
    }) as Promise<Report[]>,
}

// ── CRUD API ──────────────────────────────────────────────────

export const reportCrudApi = {
  /** 写入报告 */
  add: (report: Record<string, unknown>) =>
    client.post("/api/reports", report) as Promise<{ success: boolean; id: string }>,

  /** 删除报告 */
  delete: (reportId: string) =>
    client.delete(`/api/reports/${reportId}`) as Promise<{ success: boolean; id: string }>,
}

// ── 统一导出（便捷入口） ──────────────────────────────────────

export const reportApi = {
  // 日报
  getDailyReports: (params?: ReportListParams) =>
    client.get("/api/reports/daily", { params }) as Promise<Report[]>,

  getDailyReport: (date: string) =>
    client.get(`/api/reports/daily/${date}`) as Promise<Report>,

  generateDailyReport: () =>
    client.post("/api/reports/daily/generate") as Promise<{ success: boolean; report: string }>,

  // 月报
  getMonthlyReports: (params?: ReportListParams) =>
    client.get("/api/reports/monthly", { params }) as Promise<Report[]>,

  getMonthlyReport: (yearMonth: string) =>
    client.get(`/api/reports/monthly/${yearMonth}`) as Promise<Report>,

  generateMonthlyReport: () =>
    client.post("/api/reports/monthly/generate") as Promise<{ success: boolean; report: string }>,

  // 年报
  getAnnualReports: (params?: ReportListParams) =>
    client.get("/api/reports/annual", { params }) as Promise<Report[]>,

  getAnnualReport: (year: string) =>
    client.get(`/api/reports/annual/${year}`) as Promise<Report>,

  generateAnnualReport: () =>
    client.post("/api/reports/annual/generate") as Promise<{ success: boolean; report: string }>,

  // 统一检索
  searchReports: (query: string, reportType?: string) =>
    client.post("/api/reports/search", {
      keyword: query,
      type: reportType || "all",
    }) as Promise<Report[]>,

  // CRUD
  addReport: (report: Record<string, unknown>) =>
    client.post("/api/reports", report) as Promise<{ success: boolean; id: string }>,

  deleteReport: (reportId: string) =>
    client.delete(`/api/reports/${reportId}`) as Promise<{ success: boolean; id: string }>,
}
