/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 下单请求
 */
export type PlaceOrderRequest = {
    /**
     * 股票代码
     */
    symbol: string;
    /**
     * 买卖方向
     */
    side?: string;
    /**
     * 订单类型
     */
    type?: string;
    /**
     * 价格
     */
    price?: number;
    /**
     * 数量
     */
    quantity?: number;
    /**
     * 幂等键
     */
    idempotencyKey?: (string | null);
};

