/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Body_login_api_auth_login_post } from '../models/Body_login_api_auth_login_post';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuthService {
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
}
