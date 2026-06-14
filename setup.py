# -*- coding: utf-8 -*-
"""StockQuant 2.0 — 机构级量化交易平台"""

from setuptools import setup, find_packages

setup(
    name="stockquant",
    version="2.0.0-dev",
    packages=find_packages(exclude=["tests*", "logs*", "build*", "*.egg-info*"]),
    packages=[
        "stockquant",
        "stockquant.engine",
        "stockquant.strategy",
        "stockquant.indicators",
        "stockquant.models",
        "stockquant.analytics",
        "stockquant.data",
        "stockquant.data.providers",
        "stockquant.execution",
        "stockquant.execution.notifier",
        "stockquant.utils",
    ],
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.24",
        "pandas>=2.0",
        "requests>=2.28",
        "concurrent-log-handler>=0.9",
        "colorlog>=6.0",
        "matplotlib>=3.5",
        "jinja2>=3.0",
    ],
    extras_require={
        "talib": ["talib>=0.4"],
        "pandas-ta": ["pandas-ta>=0.3"],
        "plotly": ["plotly>=5.0"],
        "baostock": ["baostock>=0.8"],
        "pyarrow": ["pyarrow>=12.0"],
        "dev": ["pytest>=7.0", "ruff>=0.1", "coverage>=7.0"],
        "ai": ["openai>=1.0", "anthropic>=0.18", "httpx>=0.25"],
        "web": ["fastapi>=0.100", "uvicorn>=0.20", "pydantic>=2.0"],
    },
    url="https://github.com/fssl168/quantclaw",
    author="Gary-Hertel",
    author_email="garyhertel@foxmail.com",
    license="MIT",
    keywords=["stockquant", "quant", "framework", "backtest", "AI"],
    description="Professional AI-native quantitative trading platform for China A-shares",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
)
