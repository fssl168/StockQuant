/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MonitorService {
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
}
