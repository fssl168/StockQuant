/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GenerateStrategyRequest } from '../models/GenerateStrategyRequest';
import type { SaveMessageRequest } from '../models/SaveMessageRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AiService {
    /**
     * 社交媒体情绪分析
     * 分析指定股票的市场情绪。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static sentimentAnalysisApiAiSentimentGet({
        symbol = 'sh600519',
    }: {
        /**
         * 股票代码
         */
        symbol?: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/ai/sentiment',
            query: {
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 社交媒体情绪分析
     * 分析指定股票的市场情绪。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static sentimentAnalysisApiAiSentimentGet1({
        symbol = 'sh600519',
    }: {
        /**
         * 股票代码
         */
        symbol?: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/ai/sentiment',
            query: {
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * AI 生成策略代码
     * AI 生成量化交易策略代码。
     *
     * 请求体:
     * description: str — 策略描述（自然语言）
     * strategy_type: str — 策略类型（可选）: "trend", "mean_reversion", "momentum", "arbitrage"
     * @returns any Successful Response
     * @throws ApiError
     */
    public static generateStrategyApiAiStrategyGeneratePost({
        requestBody,
    }: {
        requestBody: GenerateStrategyRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/strategy/generate',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * AI 生成策略代码
     * AI 生成量化交易策略代码。
     *
     * 请求体:
     * description: str — 策略描述（自然语言）
     * strategy_type: str — 策略类型（可选）: "trend", "mean_reversion", "momentum", "arbitrage"
     * @returns any Successful Response
     * @throws ApiError
     */
    public static generateStrategyApiAiStrategyGeneratePost1({
        requestBody,
    }: {
        requestBody: GenerateStrategyRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/strategy/generate',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 会话列表
     * 列出所有会话（从数据库读取）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listConversationsApiAiConversationsGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/ai/conversations',
        });
    }
    /**
     * 会话列表
     * 列出所有会话（从数据库读取）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listConversationsApiAiConversationsGet1(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/ai/conversations',
        });
    }
    /**
     * 会话详情
     * 获取会话历史（从数据库读取）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getConversationApiAiConversationConversationIdGet({
        conversationId,
        limit = 50,
    }: {
        conversationId: string,
        limit?: number,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/ai/conversation/{conversation_id}',
            path: {
                'conversation_id': conversationId,
            },
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 会话详情
     * 获取会话历史（从数据库读取）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getConversationApiAiConversationConversationIdGet1({
        conversationId,
        limit = 50,
    }: {
        conversationId: string,
        limit?: number,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/ai/conversation/{conversation_id}',
            path: {
                'conversation_id': conversationId,
            },
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 清空会话
     * 清空会话（从数据库删除所有消息）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static clearConversationApiAiConversationConversationIdDelete({
        conversationId,
    }: {
        conversationId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/ai/conversation/{conversation_id}',
            path: {
                'conversation_id': conversationId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 清空会话
     * 清空会话（从数据库删除所有消息）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static clearConversationApiAiConversationConversationIdDelete1({
        conversationId,
    }: {
        conversationId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/ai/conversation/{conversation_id}',
            path: {
                'conversation_id': conversationId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 保存消息
     * 发送消息获取 AI 回复（非流式）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static saveMessageApiAiConversationConversationIdMessagePost({
        conversationId,
        requestBody,
    }: {
        conversationId: string,
        requestBody: SaveMessageRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/conversation/{conversation_id}/message',
            path: {
                'conversation_id': conversationId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 保存消息
     * 发送消息获取 AI 回复（非流式）。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static saveMessageApiAiConversationConversationIdMessagePost1({
        conversationId,
        requestBody,
    }: {
        conversationId: string,
        requestBody: SaveMessageRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/conversation/{conversation_id}/message',
            path: {
                'conversation_id': conversationId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询市场数据
     * 查询市场数据。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static toolQueryMarketDataApiAiToolsQueryMarketDataPost({
        symbol,
        days = 30,
    }: {
        symbol: string,
        days?: number,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/tools/query_market_data',
            query: {
                'symbol': symbol,
                'days': days,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 查询市场数据
     * 查询市场数据。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static toolQueryMarketDataApiAiToolsQueryMarketDataPost1({
        symbol,
        days = 30,
    }: {
        symbol: string,
        days?: number,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/tools/query_market_data',
            query: {
                'symbol': symbol,
                'days': days,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 搜索新闻
     * 搜索新闻。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static toolSearchNewsApiAiToolsSearchNewsPost({
        symbol,
        limit = 5,
    }: {
        symbol: string,
        limit?: number,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/tools/search_news',
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
     * 搜索新闻
     * 搜索新闻。
     * @returns any Successful Response
     * @throws ApiError
     */
    public static toolSearchNewsApiAiToolsSearchNewsPost1({
        symbol,
        limit = 5,
    }: {
        symbol: string,
        limit?: number,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/tools/search_news',
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
     * AI 解读回测结果
     * AI 解读回测结果 — 返回结构化分析（策略概述 / 过拟合风险 / Alpha来源 / 改进建议）
     * @returns any Successful Response
     * @throws ApiError
     */
    public static analyzeBacktestApiAiAnalyzeBacktestBacktestIdPost({
        backtestId,
    }: {
        backtestId: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/analyze-backtest/{backtest_id}',
            path: {
                'backtest_id': backtestId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * AI 解读回测结果
     * AI 解读回测结果 — 返回结构化分析（策略概述 / 过拟合风险 / Alpha来源 / 改进建议）
     * @returns any Successful Response
     * @throws ApiError
     */
    public static analyzeBacktestApiAiAnalyzeBacktestBacktestIdPost1({
        backtestId,
    }: {
        backtestId: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/ai/analyze-backtest/{backtest_id}',
            path: {
                'backtest_id': backtestId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取管线配置
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getConfigApiPipelineConfigGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/pipeline/config',
        });
    }
    /**
     * 更新管线配置
     * @returns any Successful Response
     * @throws ApiError
     */
    public static updateConfigApiPipelineConfigPut({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/pipeline/config',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 运行完整信息处理管线
     * @returns any Successful Response
     * @throws ApiError
     */
    public static runPipelineApiPipelineRunPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/pipeline/run',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 仅执行采集阶段
     * @returns any Successful Response
     * @throws ApiError
     */
    public static runCollectApiPipelineCollectPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/pipeline/collect',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取管线运行状态
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getTaskStatusApiPipelineStatusTaskIdGet({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/pipeline/status/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * 获取管线所有运行任务
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listTasksApiPipelineStatusGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/pipeline/status',
        });
    }
}
