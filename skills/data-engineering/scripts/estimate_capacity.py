#!/usr/bin/env python3
"""Estimate ingest, retained storage, file counts, and backfill throughput."""

from __future__ import annotations

import argparse
import json


SECONDS_PER_DAY = 86_400
MIB = 1024**2
GIB = 1024**3
TIB = 1024**4


def positive(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def nonnegative(value: str) -> float:
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-per-day", type=positive, required=True)
    parser.add_argument("--avg-record-bytes", type=positive, required=True)
    parser.add_argument("--peak-multiplier", type=positive, default=3.0)
    parser.add_argument("--retention-days", type=positive, default=30.0)
    parser.add_argument(
        "--compression-ratio",
        type=positive,
        default=0.35,
        help="Physical bytes divided by logical bytes (0.35 means 65%% compression)",
    )
    parser.add_argument("--replication-factor", type=positive, default=1.0)
    parser.add_argument("--target-file-mib", type=positive, default=256.0)
    parser.add_argument("--headroom", type=nonnegative, default=0.40, help="Fractional headroom")
    parser.add_argument("--backfill-days", type=nonnegative, default=0.0)
    parser.add_argument("--backfill-hours", type=positive, default=24.0)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser.parse_args()


def estimate(args: argparse.Namespace) -> dict:
    logical_daily = args.records_per_day * args.avg_record_bytes
    physical_daily = logical_daily * args.compression_ratio * args.replication_factor
    retained = physical_daily * args.retention_days
    avg_records_per_second = args.records_per_day / SECONDS_PER_DAY
    peak_records_per_second = avg_records_per_second * args.peak_multiplier * (1 + args.headroom)
    peak_mib_per_second = (
        peak_records_per_second * args.avg_record_bytes / MIB
    )
    target_file_bytes = args.target_file_mib * MIB
    files_per_day = physical_daily / target_file_bytes
    backfill_records = args.records_per_day * args.backfill_days
    backfill_logical = logical_daily * args.backfill_days
    backfill_seconds = args.backfill_hours * 3600
    backfill_records_per_second = backfill_records / backfill_seconds
    backfill_mib_per_second = backfill_logical / backfill_seconds / MIB

    return {
        "inputs": {
            "recordsPerDay": args.records_per_day,
            "averageRecordBytes": args.avg_record_bytes,
            "peakMultiplier": args.peak_multiplier,
            "retentionDays": args.retention_days,
            "compressionRatioPhysicalToLogical": args.compression_ratio,
            "replicationFactor": args.replication_factor,
            "targetFileMiB": args.target_file_mib,
            "headroomFraction": args.headroom,
            "backfillDays": args.backfill_days,
            "backfillHours": args.backfill_hours,
        },
        "steadyState": {
            "averageRecordsPerSecond": round(avg_records_per_second, 3),
            "peakRecordsPerSecondWithHeadroom": round(peak_records_per_second, 3),
            "peakLogicalMiBPerSecondWithHeadroom": round(peak_mib_per_second, 3),
            "logicalGiBPerDay": round(logical_daily / GIB, 3),
            "physicalGiBPerDay": round(physical_daily / GIB, 3),
            "retainedPhysicalTiB": round(retained / TIB, 3),
            "targetFilesPerDay": round(files_per_day, 2),
        },
        "backfill": {
            "logicalTiB": round(backfill_logical / TIB, 3),
            "requiredRecordsPerSecond": round(backfill_records_per_second, 3),
            "requiredLogicalMiBPerSecond": round(backfill_mib_per_second, 3),
            "note": "Backfill throughput excludes compression, retries, reads, writes, and downstream limits; add measured efficiency and live-workload constraints.",
        },
    }


def render_text(result: dict) -> str:
    steady = result["steadyState"]
    backfill = result["backfill"]
    return "\n".join(
        [
            f"Average records/s: {steady['averageRecordsPerSecond']}",
            f"Peak records/s with headroom: {steady['peakRecordsPerSecondWithHeadroom']}",
            f"Logical GiB/day: {steady['logicalGiBPerDay']}",
            f"Physical GiB/day: {steady['physicalGiBPerDay']}",
            f"Retained physical TiB: {steady['retainedPhysicalTiB']}",
            f"Target files/day: {steady['targetFilesPerDay']}",
            f"Backfill logical TiB: {backfill['logicalTiB']}",
            f"Backfill required records/s: {backfill['requiredRecordsPerSecond']}",
            f"Backfill required logical MiB/s: {backfill['requiredLogicalMiBPerSecond']}",
        ]
    )


def main() -> int:
    args = parse_args()
    if args.compression_ratio > 1:
        raise SystemExit("error: --compression-ratio should normally be <= 1")
    result = estimate(args)
    print(json.dumps(result, indent=2) if args.format == "json" else render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
