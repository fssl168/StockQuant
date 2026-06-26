/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BacktestResult = {
    taskId: string;
    status: string;
    strategyName: string;
    metrics?: Record<string, any>;
    trades?: Array<any>;
    equityCurve?: Array<any>;
    dates?: Array<any>;
    benchmark?: string;
    benchmarkMetrics?: Record<string, any>;
    benchmarkEquityCurve?: Array<any>;
    error?: string;
};

