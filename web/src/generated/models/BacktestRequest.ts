/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CommissionType } from './CommissionType';
import type { SlippageType } from './SlippageType';
/**
 * 提交回测任务的请求
 */
export type BacktestRequest = {
    /**
     * 策略名称
     */
    strategyName: string;
    /**
     * 策略 Python 代码
     */
    strategyCode: string;
    /**
     * 标的列表
     */
    symbols?: Array<string>;
    /**
     * 开始日期 YYYY-MM-DD
     */
    startDate: string;
    /**
     * 结束日期 YYYY-MM-DD
     */
    endDate: string;
    /**
     * 初始资金
     */
    cash?: number;
    /**
     * 佣金类型
     */
    commissionType?: CommissionType;
    /**
     * 滑点类型
     */
    slippageType?: SlippageType;
};

