#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

MODEL_ID_MAP = {
    "o3": ("openai", "o3"),
    "Claude-4.1-Opus": ("anthropic", "claude-4.1-opus"),
    "GPT-5": ("openai", "gpt-5"),
    "Claude-4-Opus": ("anthropic", "claude-4-opus"),
    "Gemini-2.5-Pro": ("google", "gemini-2.5-pro"),
    "Gemini-2.5-Flash": ("google", "gemini-2.5-flash"),
}

SOURCE_URL = "https://sciarena.allen.ai/api/leaderboard"


def make_source_data() -> dict:
    return {
        "source_type": "url",
        "dataset_name": "SciArena leaderboard API",
        "url": [SOURCE_URL],
    }


def load_rows(input_json: Path) -> list[dict]:
    return json.loads(input_json.read_text(encoding="utf-8"))


def normalize_model(raw_model_id: str) -> tuple[str, str]:
    if raw_model_id not in MODEL_ID_MAP:
        raise KeyError(
            f"No canonical mapping for modelId={raw_model_id!r}. "
            "Add it to MODEL_ID_MAP before scaling further."
        )
    return MODEL_ID_MAP[raw_model_id]


def make_results(row: dict) -> list[dict]:
    results = []

    results.append(
        {
            "evaluation_result_id": "overall::elo",
            "evaluation_name": "overall",
            "source_data": make_source_data(),
            "metric_config": {
                "metric_id": "elo",
                "metric_name": "Elo rating",
                "lower_is_better": False,
                "additional_details": {
                    "raw_metric_field": "rating",
                },
            },
            "score_details": {
                "score": float(row["rating"]),
                "details": {
                    "num_battles": str(row["num_battles"]),
                    "rating_q025": str(row["rating_q025"]),
                    "rating_q975": str(row["rating_q975"]),
                },
            },
        }
    )

    results.append(
        {
            "evaluation_result_id": "overall::rank",
            "evaluation_name": "overall",
            "source_data": make_source_data(),
            "metric_config": {
                "metric_id": "rank",
                "metric_name": "Rank",
                "lower_is_better": True,
            },
            "score_details": {
                "score": float(row["rank"]),
            },
        }
    )

    if row.get("cost_per_100_calls_usd") is not None:
        results.append(
            {
                "evaluation_result_id": "overall::cost_per_100_calls_usd",
                "evaluation_name": "overall",
                "source_data": make_source_data(),
                "metric_config": {
                    "metric_id": "cost_per_100_calls_usd",
                    "metric_name": "Cost per 100 calls",
                    "lower_is_better": True,
                },
                "score_details": {
                    "score": float(row["cost_per_100_calls_usd"]),
                },
            }
        )

    return results


def make_log(row: dict) -> tuple[dict, str, str]:
    raw_model_id = row["modelId"]
    developer_name, model_name = normalize_model(raw_model_id)
    ts = str(time.time())

    log = {
        "schema_version": "0.2.2",
        "evaluation_id": f"sciarena/{developer_name}/{model_name}/{ts}",
        "retrieved_timestamp": ts,
        "source_metadata": {
            "source_name": "SciArena leaderboard API",
            "source_type": "documentation",
            "source_organization_name": "Ai2",
            "source_organization_url": "https://sciarena.allen.ai",
            "evaluator_relationship": "third_party",
            "additional_details": {
                "api_endpoint": SOURCE_URL,
            },
        },
        "eval_library": {
            "name": "SciArena",
            "version": "unknown",
        },
        "model_info": {
            "name": raw_model_id,
            "id": f"{developer_name}/{model_name}",
            "developer": developer_name,
            "additional_details": {
                "raw_model_id": raw_model_id,
            },
        },
        "evaluation_results": make_results(row),
    }
    return log, developer_name, model_name


def write_log(log: dict, out_root: Path, developer: str, model: str) -> Path:
    out_dir = out_root / "sciarena" / developer / model
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{uuid.uuid4()}.json"
    out_path.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    return out_path


def export_one(row: dict, out_root: Path) -> Path:
    log, developer, model = make_log(row)
    return write_log(log, out_root, developer, model)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Exact SciArena modelId to export. If omitted, export all mapped models.",
    )
    args = parser.parse_args()

    rows = load_rows(args.input_json)

    if args.model is not None:
        matches = [row for row in rows if row["modelId"] == args.model]
        if not matches:
            raise SystemExit(f"Model {args.model!r} not found in {args.input_json}")
        print(export_one(matches[0], args.output_dir))
        return

    exported = 0
    for row in rows:
        raw_model_id = row["modelId"]
        if raw_model_id not in MODEL_ID_MAP:
            continue
        out_path = export_one(row, args.output_dir)
        print(out_path)
        exported += 1

    print(f"Exported {exported} model(s).")


if __name__ == "__main__":
    main()
