/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 添加信号请求
 */
export type AddSignalRequest = {
    /**
     * 股票代码
     */
    symbol: string;
    /**
     * 方向
     */
    side?: string;
    /**
     * 信号来源
     */
    source?: string;
    /**
     * 置信度
     */
    confidence?: number;
    /**
     * 理由
     */
    reason?: string;
    /**
     * 价格
     */
    price?: (number | null);
    /**
     * 数量
     */
    quantity?: (number | null);
};

