/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AccountSummaryResponse } from '../models/AccountSummaryResponse';
import type { AddSignalRequest } from '../models/AddSignalRequest';
import type { BacktestRequest } from '../models/BacktestRequest';
import type { BacktestResult } from '../models/BacktestResult';
import type { Body_login_api_auth_login_post } from '../models/Body_login_api_auth_login_post';
import type { Body_upload_csv_api_data_upload_csv_post } from '../models/Body_upload_csv_api_data_upload_csv_post';
import type { CollectDataRequest } from '../models/CollectDataRequest';
import type { CompareStrategiesRequest } from '../models/CompareStrategiesRequest';
import type { DashboardMetrics } from '../models/DashboardMetrics';
import type { MessageResponse } from '../models/MessageResponse';
import type { PlaceOrderRequest } from '../models/PlaceOrderRequest';
import type { SchedulerStatusResponse } from '../models/SchedulerStatusResponse';
import type { SettingsSaveRequest } from '../models/SettingsSaveRequest';
import type { StrategyCreate } from '../models/StrategyCreate';
import type { StrategyInfo } from '../models/StrategyInfo';
import type { TaskCreate } from '../models/TaskCreate';
import type { TaskResponse } from '../models/TaskResponse';
import type { UpdateDataRequest } from '../models/UpdateDataRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class Service {
    /**
     * 回测任务列表
     * 获取所有回测任务（按创建时间倒序）
     * @returns BacktestResult Successful Response
     * @throws ApiError
     */
    public static listBacktestsApiBacktestGet(): CancelablePromise<Array<BacktestResult>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/backtest',
        });
    }
    /**
     * 提交回测任务
     * 提交回测任务，使用 Celery 异步执行
     * @returns TaskResponse Successful Response
     * @throws ApiError
     */
    public static submitBacktestApiBacktestPost({
        requestBody,
    }: {
        requestBody: BacktestRequest,
    }): CancelablePromise<TaskResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/backtest',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 回测结果
     * 获取指定回测任务的结果
     * @returns BacktestResult Successful Response
     * @throws ApiError
     */
    public static getBacktestApiBacktestTaskIdGet({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<BacktestResult> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/backtest/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 删除回测任务
     * 删除回测任务
     * @returns MessageResponse Successful Response
     * @throws ApiError
     */
    public static deleteBacktestApiBacktestTaskIdDelete({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<MessageResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/backtest/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 导出回测报告
     * 生成回测报告（HTML / JSON / PDF）
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getBacktestReportApiBacktestTaskIdReportGet({
        taskId,
        format = 'html',
    }: {
        taskId: string,
        /**
         * 报告格式: html|json|pdf
         */
        format?: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/backtest/{task_id}/report',
            path: {
                'task_id': taskId,
            },
            query: {
                'format': format,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 模拟盘vs回测对比
     * 对比模拟盘实绩与回测结果
     * @returns any Successful Response
     * @throws ApiError
     */
    public static comparePaperVsBacktestApiBacktestComparePaperPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/backtest/compare-paper',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 策略列表
     * 获取所有策略
     * @returns StrategyInfo Successful Response
     * @throws ApiError
     */
    public static listStrategiesApiStrategyGet(): CancelablePromise<Array<StrategyInfo>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/strategy',
        });
    }
    /**
     * 创建策略
     * 创建策略。
     *
     * MVP 将策略代码以字符串形式存储，暂不验证语法。
     * @returns StrategyInfo Successful Response
     * @throws ApiError
     */
    public static createStrategyApiStrategyPost({
        requestBody,
    }: {
        requestBody: StrategyCreate,
    }): CancelablePromise<StrategyInfo> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/strategy',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 策略详情
     * 获取指定策略的详细信息
     * @returns StrategyInfo Successful Response
     * @throws ApiError
     */
    public static getStrategyApiStrategyStrategyIdGet({
        strategyId,
    }: {
        strategyId: string,
    }): CancelablePromise<StrategyInfo> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/strategy/{strategy_id}',
            path: {
                'strategy_id': strategyId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 更新策略
     * 更新策略
     * @returns StrategyInfo Successful Response
     * @throws ApiError
     */
    public static updateStrategyApiStrategyStrategyIdPut({
        strategyId,
        requestBody,
    }: {
        strategyId: string,
        requestBody: Record<string, any>,
    }): CancelablePromise<StrategyInfo> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/strategy/{strategy_id}',
            path: {
                'strategy_id': strategyId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 删除策略
     * 删除策略
     * @returns MessageResponse Successful Response
     * @throws ApiError
     */
    public static deleteStrategyApiStrategyStrategyIdDelete({
        strategyId,
    }: {
        strategyId: string,
    }): CancelablePromise<MessageResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/strategy/{strategy_id}',
            path: {
                'strategy_id': strategyId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 仪表盘核心指标
     * 返回聚合仪表盘指标。
     * 优先从 trading.py 获取实盘/模拟盘真实持仓数据；
     * 若无实盘数据，则从已完成回测任务中提取汇总数据。
     * @returns DashboardMetrics Successful Response
     * @throws ApiError
     */
    public static getDashboardMetricsApiDashboardMetricsGet(): CancelablePromise<DashboardMetrics> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/dashboard/metrics',
        });
    }
    /**
     * 仪表盘信号列表
     * 返回最近的交易信号列表（供仪表盘展示）
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getDashboardSignalsApiDashboardSignalsGet(): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/dashboard/signals',
        });
    }
    /**
     * Get Watchlist
     * 获取自选股列表
     * @returns string Successful Response
     * @throws ApiError
     */
    public static getWatchlistApiMonitorWatchlistGet(): CancelablePromise<Array<string>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/watchlist',
        });
    }
    /**
     * Add To Watchlist
     * 添加到自选股
     * @returns string Successful Response
     * @throws ApiError
     */
    public static addToWatchlistApiMonitorWatchlistPost({
        requestBody,
    }: {
        requestBody: Array<string>,
    }): CancelablePromise<Array<string>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/monitor/watchlist',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Remove From Watchlist
     * 从自选股移除
     * @returns string Successful Response
     * @throws ApiError
     */
    public static removeFromWatchlistApiMonitorWatchlistDelete({
        requestBody,
    }: {
        requestBody: Array<string>,
    }): CancelablePromise<Array<string>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/monitor/watchlist',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Alerts
     * 获取告警记录
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getAlertsApiMonitorAlertsGet({
        limit = 50,
    }: {
        limit?: number,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/alerts',
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Scan Symbol
     * 扫描指定股票信号
     * @returns any Successful Response
     * @throws ApiError
     */
    public static scanSymbolApiMonitorScanSymbolGet({
        symbol,
    }: {
        symbol: string,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/scan/{symbol}',
            path: {
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Pre Market Brief
     * 获取盘前简报
     * @returns string Successful Response
     * @throws ApiError
     */
    public static preMarketBriefApiMonitorBriefGet({
        requestBody,
    }: {
        requestBody?: (Array<string> | null),
    }): CancelablePromise<string> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/brief',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Post Market Summary
     * 获取收盘总结
     * @returns string Successful Response
     * @throws ApiError
     */
    public static postMarketSummaryApiMonitorSummaryGet(): CancelablePromise<string> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/summary',
        });
    }
    /**
     * Get Status
     * 获取监控状态
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getStatusApiMonitorStatusGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/status',
        });
    }
    /**
     * Start Monitoring
     * 启动实时扫描
     * @returns string Successful Response
     * @throws ApiError
     */
    public static startMonitoringApiMonitorStartMonitoringPost({
        requestBody,
    }: {
        requestBody?: (Record<string, any> | null),
    }): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/monitor/start-monitoring',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get News Correlation
     * F024 消息面联动 — 新闻-持仓联动分析
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getNewsCorrelationApiMonitorNewsCorrelationGet({
        requestBody,
    }: {
        requestBody?: (Array<string> | null),
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/news-correlation',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Fused Signals
     * F024 AI 信号融合 — 技术面+情绪面+基本面三源融合
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getFusedSignalsApiMonitorFusedSignalsGet({
        requestBody,
    }: {
        requestBody?: (Array<string> | null),
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/fused-signals',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Stop Monitoring
     * 停止实时扫描
     * @returns string Successful Response
     * @throws ApiError
     */
    public static stopMonitoringApiMonitorStopMonitoringPost(): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/monitor/stop-monitoring',
        });
    }
    /**
     * Get Premarket Briefing
     * 获取盘前简报（结构化）。
     *
     * 包含隔夜全球市场概览、自选股关键新闻、技术关键位、建议关注标的。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getPremarketBriefingApiMonitorPremarketBriefingGet({
        requestBody,
    }: {
        requestBody?: (Array<string> | null),
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/premarket-briefing',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Postmarket Summary
     * 获取收盘总结（结构化）。
     *
     * 包含大盘指数表现、自选股表现、异动与成交量、当日关键信号、次日催化剂预览。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getPostmarketSummaryApiMonitorPostmarketSummaryGet({
        requestBody,
    }: {
        requestBody?: (Array<string> | null),
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/postmarket-summary',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Sentiment Analysis
     * 获取指定股票的情绪分析。
     *
     * 基于新闻文本进行关键词情绪评分，并检测情绪突变。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSentimentAnalysisApiMonitorSentimentSymbolGet({
        symbol,
    }: {
        symbol: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/sentiment/{symbol}',
            path: {
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Risk Control
     * 获取动态风控参数。
     *
     * 基于沪深300近20日波动率判断市场环境，动态调整风控参数。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getRiskControlApiMonitorRiskControlGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/monitor/risk-control',
        });
    }
    /**
     * 多策略对比
     * 对比多个策略的回测结果。
     *
     * 请求体:
     * strategy_ids: list[str] — 回测任务 ID 列表（至少 2 个）
     * @returns any Successful Response
     * @throws ApiError
     */
    public static compareStrategiesApiComparisonPost({
        requestBody,
    }: {
        requestBody: CompareStrategiesRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/comparison',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 对比历史
     * 获取历史对比结果（最新的在前），使用 ComparisonHistoryStore
     * @returns any Successful Response
     * @throws ApiError
     */
    public static comparisonHistoryApiComparisonHistoryGet(): CancelablePromise<Array<any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/comparison/history',
        });
    }
    /**
     * 组合优化
     * 策略组合优化 — 相关性+最优权重。
     *
     * 请求体:
     * strategy_ids: list[str] — 回测任务 ID 列表（至少 2 个）
     * @returns any Successful Response
     * @throws ApiError
     */
    public static optimizePortfolioApiComparisonOptimizePost({
        requestBody,
    }: {
        requestBody: CompareStrategiesRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/comparison/optimize',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 生命周期建议
     * 策略生命周期建议 — 启用/停用/调整。
     *
     * 基于近 30 天表现给出建议。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static lifecycleAdviceApiComparisonLifecycleStrategyIdGet({
        strategyId,
    }: {
        strategyId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/comparison/lifecycle/{strategy_id}',
            path: {
                'strategy_id': strategyId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 通知列表
     * 获取通知列表，支持 ?type= 过滤，最新优先。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getNotificationsApiNotificationsGet({
        type,
    }: {
        /**
         * 按类型过滤: signal / alert / info
         */
        type?: (string | null),
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/notifications',
            query: {
                'type': type,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 标记已读
     * 标记通知为已读。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static markAsReadApiNotificationsNotificationIdReadPut({
        notificationId,
    }: {
        notificationId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/notifications/{notification_id}/read',
            path: {
                'notification_id': notificationId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 删除通知
     * 删除指定通知。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static deleteNotificationApiNotificationsNotificationIdDelete({
        notificationId,
    }: {
        notificationId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/notifications/{notification_id}',
            path: {
                'notification_id': notificationId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取数据源列表
     * Return dynamically resolved data sources.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSourcesApiDataSourcesGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/data/sources',
        });
    }
    /**
     * 获取数据源列表
     * Update data source config.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static updateSourceApiDataSourcesPost({
        requestBody,
    }: {
        requestBody: UpdateDataRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/data/sources',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取数据源列表
     * Update data source config.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static updateSourceByProviderApiDataSourcesProviderPut({
        provider,
        requestBody,
    }: {
        provider: string,
        requestBody: UpdateDataRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/data/sources/{provider}',
            path: {
                'provider': provider,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 删除数据源
     * Remove a data source (no-op for now - sources are dynamic).
     * @returns any Successful Response
     * @throws ApiError
     */
    public static deleteSourceApiDataSourcesProviderDelete({
        provider,
    }: {
        provider: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/data/sources/{provider}',
            path: {
                'provider': provider,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 缓存统计
     * Return cache statistics.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getCacheStatsApiDataCacheGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/data/cache',
        });
    }
    /**
     * 清除缓存
     * Clear all K-line cache.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static clearCacheApiDataCacheDelete(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/data/cache',
        });
    }
    /**
     * 查询K线数据
     * Fetch K-line OHLCV data via DataService with proper async handling.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getKlineApiDataKlineGet({
        symbol,
        start,
        end,
        timeframe = '1d',
        source = '',
    }: {
        /**
         * 股票代码
         */
        symbol: string,
        /**
         * 开始日期 YYYY-MM-DD
         */
        start: string,
        /**
         * 结束日期 YYYY-MM-DD
         */
        end: string,
        /**
         * 时间周期
         */
        timeframe?: string,
        /**
         * 数据源名称(不传则默认DataService)
         */
        source?: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/data/kline',
            query: {
                'symbol': symbol,
                'start': start,
                'end': end,
                'timeframe': timeframe,
                'source': source,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 手动触发数据采集
     * Start data collection task.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static collectDataApiDataCollectPost({
        requestBody,
    }: {
        requestBody: CollectDataRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/data/collect',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取数据源健康状态
     * Return health status of all configured data sources.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getDataHealthApiDataHealthGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/data/health',
        });
    }
    /**
     * 数据采集日志
     * Return recent collect task logs (last 20, sorted by created_at desc).
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getCollectLogsApiDataCollectLogsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/data/collect-logs',
        });
    }
    /**
     * 批量下载
     * Download K-line data for default symbols from a provider.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static downloadDataApiDataDownloadGet({
        provider,
    }: {
        /**
         * 数据源名称
         */
        provider: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/data/download',
            query: {
                'provider': provider,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 上传 CSV 数据文件
     * Upload and import CSV K-line data.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static uploadCsvApiDataUploadCsvPost({
        formData,
    }: {
        formData: Body_upload_csv_api_data_upload_csv_post,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/data/upload-csv',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取全部配置
     * 获取所有配置项，敏感值掩码显示，附带来源信息
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSettingsApiSettingsGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/settings',
        });
    }
    /**
     * 保存配置
     * 批量保存配置 — 持久化到 JSON 文件，敏感值自动加密
     * @returns any Successful Response
     * @throws ApiError
     */
    public static saveSettingsApiSettingsSavePost({
        requestBody,
    }: {
        requestBody: SettingsSaveRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/settings/save',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 恢复配置默认值
     * 恢复单个配置项为 .env 值（优先）或代码默认值
     * @returns any Successful Response
     * @throws ApiError
     */
    public static resetSettingApiSettingsKeyDelete({
        key,
    }: {
        key: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/settings/{key}',
            path: {
                'key': key,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取所有可配置项
     * 获取所有可配置项及其默认值和来源
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSettingsSourcesApiSettingsSourcesGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/settings/sources',
        });
    }
    /**
     * 获取管理员白名单
     * 获取管理员白名单
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getWhitelistApiSettingsWhitelistGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/settings/whitelist',
        });
    }
    /**
     * 配置健康状态
     * 获取配置健康状态
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSettingsHealthApiSettingsHealthGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/settings/health',
        });
    }
    /**
     * 账户信息
     * 获取账户信息 — 从 Portfolio 模型读取
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getAccountApiTradingAccountGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/trading/account',
        });
    }
    /**
     * 下单
     * 提交订单 — 通过 PaperBroker 撮合
     * @returns any Successful Response
     * @throws ApiError
     */
    public static placeOrderApiTradingOrderPost({
        requestBody,
    }: {
        requestBody: PlaceOrderRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/trading/order',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 撤单
     * 撤销订单 — 从 pending limit 订单簿或订单审计中查找
     * @returns any Successful Response
     * @throws ApiError
     */
    public static cancelOrderApiTradingOrderOrderIdDelete({
        orderId,
    }: {
        orderId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/trading/order/{order_id}',
            path: {
                'order_id': orderId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 持仓列表
     * 获取当前持仓 — 从 Portfolio 模型读取
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getPositionsApiTradingPositionsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/trading/positions',
        });
    }
    /**
     * 成交记录
     * 获取成交记录 — 从 PaperBroker trade_log 读取
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getTradesApiTradingTradesGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/trading/trades',
        });
    }
    /**
     * 订单列表
     * 获取订单列表 — 合并审计日志 + pending limit 订单
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getOrdersApiTradingOrdersGet(): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/trading/orders',
        });
    }
    /**
     * 账户连接状态
     * 获取当前券商配置下的账户连接状态。
     *
     * 测试当前券商配置（trading.broker + trading.api）下的连接状态，
     * 返回余额和持仓摘要。如果券商 SDK 未连接，显示模拟模式。
     * @returns AccountSummaryResponse Successful Response
     * @throws ApiError
     */
    public static getAccountStatusApiTradingAccountStatusGet(): CancelablePromise<AccountSummaryResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/trading/account-status',
        });
    }
    /**
     * 风控状态
     * 获取当前风控状态和历史事件。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getRiskStatusApiTradingRiskStatusGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/trading/risk/status',
        });
    }
    /**
     * 恢复交易
     * 恢复被熔断的交易。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static resumeTradingApiTradingRiskResumePost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/trading/risk/resume',
        });
    }
    /**
     * 风控报告
     * 获取动态风控报告 — 参数调整历史 + 异常检测 + 黑天鹅状态
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getRiskReportEndpointApiTradingRiskReportGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/trading/risk/report',
        });
    }
    /**
     * 持仓列表
     * 获取持仓列表 — 来自真实交易数据
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getPositionsApiPortfolioPositionsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/portfolio/positions',
        });
    }
    /**
     * 账户汇总
     * 获取账户汇总信息 — 来自真实交易数据
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getAccountApiPortfolioAccountGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/portfolio/account',
        });
    }
    /**
     * 行业分布
     * 获取行业分布 — 基于持仓动态计算
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSectorApiPortfolioSectorGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/portfolio/sector',
        });
    }
    /**
     * 盈亏分析
     * 获取盈亏分析 — 基于真实成交记录
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getPnlApiPortfolioPnlGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/portfolio/pnl',
        });
    }
    /**
     * 组合权益曲线
     * 获取组合整体权益曲线 — 优先快照数据，其次回测结果，最后实时交易数据
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getEquityCurveApiPortfolioEquityCurveGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/portfolio/equity-curve',
        });
    }
    /**
     * 个股权益曲线
     * 获取个股权益曲线 — 基于该标的的历史 K 线价格 + 交易记录
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getStockEquityCurveApiPortfolioEquityCurveSymbolGet({
        symbol,
    }: {
        symbol: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/portfolio/equity-curve/{symbol}',
            path: {
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 保存权益快照
     * 手动触发权益快照保存。
     *
     * 将当前账户权益状态持久化到 equity_snapshots 表，
     * 用于历史权益曲线展示和回溯分析。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static saveEquitySnapshotApiPortfolioSnapshotPost(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/portfolio/snapshot',
        });
    }
    /**
     * 组合风险指标
     * 获取组合风险指标 — 基于真实权益曲线计算
     *
     * 返回：VaR(95%)、波动率、夏普比率、最大回撤、Beta、Alpha
     * 无足够历史数据时返回零值。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getRiskMetricsApiPortfolioRiskMetricsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/portfolio/risk-metrics',
        });
    }
    /**
     * 提交参数优化任务
     * 提交参数优化任务，异步执行 Cerebro.optstrategy()
     * @returns any Successful Response
     * @throws ApiError
     */
    public static submitOptimizeApiBacktestOptimizePost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/backtest/optimize',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询优化状态/结果
     * 查询参数优化任务状态和结果
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getOptimizeStatusApiBacktestOptimizeTaskIdGet({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/backtest/optimize/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 用户登录
     * 用户名密码登录，返回 JWT token
     * @returns any Successful Response
     * @throws ApiError
     */
    public static loginApiAuthLoginPost({
        formData,
    }: {
        formData: Body_login_api_auth_login_post,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/auth/login',
            formData: formData,
            mediaType: 'application/x-www-form-urlencoded',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 用户注册
     * 注册新用户 — 数据持久化到数据库
     * @returns any Successful Response
     * @throws ApiError
     */
    public static registerApiAuthRegisterPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/auth/register',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取当前用户信息
     * 获取当前登录用户信息 — 从数据库读取
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getMeApiAuthMeGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/auth/me',
        });
    }
    /**
     * 获取活跃信号列表
     * 获取当前活跃信号列表，支持按标的/方向/来源过滤
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listSignalsApiSignalsGet({
        symbol,
        side,
        source,
    }: {
        symbol?: (string | null),
        side?: (string | null),
        source?: (string | null),
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/signals',
            query: {
                'symbol': symbol,
                'side': side,
                'source': source,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 手动添加信号
     * 手动添加交易信号
     * @returns any Successful Response
     * @throws ApiError
     */
    public static addSignalApiSignalsPost({
        requestBody,
    }: {
        requestBody: AddSignalRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/signals',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 移除信号
     * 移除指定信号
     * @returns any Successful Response
     * @throws ApiError
     */
    public static removeSignalApiSignalsSignalIdDelete({
        signalId,
    }: {
        signalId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/signals/{signal_id}',
            path: {
                'signal_id': signalId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 信号审计日志
     * 获取信号审计日志
     * @returns any Successful Response
     * @throws ApiError
     */
    public static signalAuditApiSignalsAuditGet({
        symbol,
        limit = 50,
    }: {
        symbol?: (string | null),
        limit?: number,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/signals/audit',
            query: {
                'symbol': symbol,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 信号统计
     * 获取信号管线统计信息
     * @returns any Successful Response
     * @throws ApiError
     */
    public static signalStatsApiSignalsStatsGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/signals/stats',
        });
    }
    /**
     * 列出所有定时任务
     * 获取所有已注册的定时任务
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listTasksApiSchedulerTasksGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/scheduler/tasks',
        });
    }
    /**
     * 添加定时任务
     * 添加新的定时任务
     * @returns any Successful Response
     * @throws ApiError
     */
    public static addTaskApiSchedulerTasksPost({
        requestBody,
    }: {
        requestBody: TaskCreate,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scheduler/tasks',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 删除定时任务
     * 删除指定定时任务
     * @returns MessageResponse Successful Response
     * @throws ApiError
     */
    public static removeTaskApiSchedulerTasksTaskIdDelete({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<MessageResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/scheduler/tasks/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 启动调度器
     * 启动调度器
     * @returns any Successful Response
     * @throws ApiError
     */
    public static startSchedulerApiSchedulerStartPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scheduler/start',
        });
    }
    /**
     * 停止调度器
     * 停止调度器
     * @returns any Successful Response
     * @throws ApiError
     */
    public static stopSchedulerApiSchedulerStopPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/scheduler/stop',
        });
    }
    /**
     * 调度器状态
     * 获取调度器运行状态
     * @returns SchedulerStatusResponse Successful Response
     * @throws ApiError
     */
    public static schedulerStatusApiSchedulerStatusGet(): CancelablePromise<SchedulerStatusResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/scheduler/status',
        });
    }
    /**
     * 操作审计日志
     * 获取操作审计日志（仅 ADMIN 可查全部）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listAuditLogsApiAuditLogsGet({
        limit = 50,
    }: {
        limit?: number,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/audit/logs',
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 全部审计日志（ADMIN）
     * 获取全部操作审计日志（需 ADMIN 权限）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listAllAuditLogsApiAuditLogsAllGet({
        limit = 50,
        userId,
        resourceType,
    }: {
        limit?: number,
        userId?: (string | null),
        resourceType?: (string | null),
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/audit/logs/all',
            query: {
                'limit': limit,
                'user_id': userId,
                'resource_type': resourceType,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Prometheus 指标
     * 返回 Prometheus 格式的指标
     * @returns any Successful Response
     * @throws ApiError
     */
    public static metricsMetricsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/metrics',
        });
    }
    /**
     * 健康检查
     * 系统健康检查
     * @returns any Successful Response
     * @throws ApiError
     */
    public static healthCheckHealthGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/health',
        });
    }
    /**
     * 获取 L1 工作记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getL1ApiMemoryL1Get({
        n = 20,
        symbol,
    }: {
        /**
         * 返回条数
         */
        n?: number,
        /**
         * 按标的过滤
         */
        symbol?: (string | null),
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/memory/l1',
            query: {
                'n': n,
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 添加 L1 工作记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static addL1ApiMemoryL1Post({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/memory/l1',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 清空 L1 工作记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static clearL1ApiMemoryL1Delete(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/memory/l1',
        });
    }
    /**
     * 获取 L2 短期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getL2ApiMemoryL2Get({
        keyword,
        symbol,
        limit = 20,
        offset,
    }: {
        /**
         * 关键词搜索
         */
        keyword?: (string | null),
        /**
         * 按标的过滤
         */
        symbol?: (string | null),
        /**
         * 返回条数
         */
        limit?: number,
        /**
         * 偏移量
         */
        offset?: number,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/memory/l2',
            query: {
                'keyword': keyword,
                'symbol': symbol,
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 写入 L2 短期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static addL2ApiMemoryL2Post({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/memory/l2',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 清空 L2 短期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static clearL2ApiMemoryL2Delete(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/memory/l2',
        });
    }
    /**
     * 搜索 L2 短期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static searchL2ApiMemoryL2SearchPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/memory/l2/search',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取 L3 长期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getL3ApiMemoryL3Get({
        keyword,
        symbol,
        minConfidence,
        limit = 20,
        offset,
    }: {
        /**
         * 关键词搜索
         */
        keyword?: (string | null),
        /**
         * 按标的过滤
         */
        symbol?: (string | null),
        /**
         * 最低置信度
         */
        minConfidence?: number,
        /**
         * 返回条数
         */
        limit?: number,
        /**
         * 偏移量
         */
        offset?: number,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/memory/l3',
            query: {
                'keyword': keyword,
                'symbol': symbol,
                'min_confidence': minConfidence,
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 写入 L3 长期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static addL3ApiMemoryL3Post({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/memory/l3',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 清空 L3 长期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static clearL3ApiMemoryL3Delete(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/memory/l3',
        });
    }
    /**
     * 搜索 L3 长期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static searchL3ApiMemoryL3SearchPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/memory/l3/search',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 触发 L2→L3 记忆压缩
     * @returns any Successful Response
     * @throws ApiError
     */
    public static compressL2ToL3ApiMemoryCompressPost(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/memory/compress',
        });
    }
    /**
     * 清理过期记忆
     * @returns any Successful Response
     * @throws ApiError
     */
    public static cleanupExpiredApiMemoryCleanupPost(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/memory/cleanup',
        });
    }
    /**
     * 获取幻觉检测配置
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getConfigApiHallucinationConfigGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/hallucination/config',
        });
    }
    /**
     * 配置幻觉检测模式
     * @returns any Successful Response
     * @throws ApiError
     */
    public static updateConfigApiHallucinationConfigPut({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/hallucination/config',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询幻觉记录
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listRecordsApiHallucinationRecordsGet({
        agent,
        hallucinationType,
        limit = 50,
    }: {
        /**
         * 按 Agent 过滤
         */
        agent?: (string | null),
        /**
         * 按类型过滤
         */
        hallucinationType?: (string | null),
        /**
         * 最大返回条数
         */
        limit?: number,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/hallucination/records',
            query: {
                'agent': agent,
                'hallucination_type': hallucinationType,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 手动记录幻觉事件
     * @returns any Successful Response
     * @throws ApiError
     */
    public static recordHallucinationApiHallucinationRecordPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/hallucination/record',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 幻觉模式分析
     * @returns any Successful Response
     * @throws ApiError
     */
    public static analyzePatternsApiHallucinationAnalysisGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/hallucination/analysis',
        });
    }
    /**
     * Prompt 优化建议
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSuggestionsApiHallucinationSuggestionsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/hallucination/suggestions',
        });
    }
}
