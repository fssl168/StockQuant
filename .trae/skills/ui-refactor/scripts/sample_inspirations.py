#!/usr/bin/env python3
import argparse
import json
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从 inspiration_pool.json 随机采样灵感来源（默认 2 个）"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=2,
        help="采样数量（默认 2）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子（可选，用于复现）",
    )
    parser.add_argument(
        "--pool",
        type=str,
        default=None,
        help="灵感池 JSON 路径（默认使用 skill 内置 references/inspiration_pool.json）",
    )
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    default_pool = skill_dir / "references" / "inspiration_pool.json"
    pool_path = Path(args.pool).resolve() if args.pool else default_pool

    data = json.loads(pool_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise SystemExit("灵感池格式错误：需要 JSON 字符串数组。")

    if args.count < 1:
        raise SystemExit("--count 必须 >= 1")
    if args.count > len(data):
        raise SystemExit(f"--count 不能超过灵感池长度（{len(data)}）")

    rng = random.Random(args.seed)
    picks = rng.sample(data, k=args.count)

    print(
        json.dumps(
            {
                "count": args.count,
                "seed": args.seed,
                "pool": str(pool_path),
                "picks": picks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
