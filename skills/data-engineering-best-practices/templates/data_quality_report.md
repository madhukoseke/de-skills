---
title: "Data Quality Report"
description: "Template for recurring data quality reporting and incident-oriented DQ analysis"
tags: [data-quality, dq-report, observability, template]
---

# Data Quality Report Template

Fill in all sections. Used by DATA_QUALITY mode and DIAGNOSE mode. Referenced by `playbooks/07_data_quality.md`.

---

## Report Metadata

**Dataset / Table:** <!-- e.g., project.mart_sales.fact_orders -->
**Pipeline:** <!-- e.g., orders_daily_load -->
**Report date:** <!-- YYYY-MM-DD -->
**Run trigger:** <!-- scheduled | ad-hoc | incident investigation -->
**Reported by:** <!-- Team or individual -->
**Data contract version:** <!-- e.g., 1.2.0 -->

---

## Executive Summary

<!-- 2-3 sentence summary of overall DQ health. State number of checks run, passed, failed, warned. -->

**Overall DQ health:** <!-- GREEN (all pass) | YELLOW (warnings) | RED (failures) -->

| Metric | Value |
|--------|-------|
| Total checks run | |
| PASS | |
| WARN | |
| FAIL | |
| Rows quarantined | |
| % rows passed DQ | |

---

## Check Results

### Freshness

| Check | Expected | Actual | Status | Action Required |
|-------|----------|--------|--------|-----------------|
| Data loaded within SLA | < 2 hours | | <!-- PASS / FAIL / WARN --> | |
| Source freshness (dbt) | < 6 hours | | <!-- PASS / FAIL --> | |

### Completeness

| Check | Expected | Actual | Status | Action Required |
|-------|----------|--------|--------|-----------------|
| Row count (today) | > N rows | | <!-- PASS / FAIL / WARN --> | |
| Row count vs yesterday | within ±20% | | <!-- PASS / FAIL --> | |
| NOT NULL: `order_id` | 0 nulls | | <!-- PASS / FAIL --> | |
| NOT NULL: `customer_id` | 0 nulls | | <!-- PASS / FAIL --> | |
| NOT NULL: `order_date` | 0 nulls | | <!-- PASS / FAIL --> | |

### Uniqueness

| Check | Expected | Actual | Status | Action Required |
|-------|----------|--------|--------|-----------------|
| `order_id` uniqueness | 0 duplicates | | <!-- PASS / FAIL --> | |
| Composite key uniqueness (if applicable) | 0 duplicates | | <!-- PASS / FAIL / N-A --> | |

### Validity

| Check | Expected | Actual | Status | Action Required |
|-------|----------|--------|--------|-----------------|
| `order_status` accepted values | Only known values | | <!-- PASS / FAIL --> | |
| `total_amount >= 0` | True for all rows | | <!-- PASS / FAIL --> | |
| `order_date <= CURRENT_DATE()` | No future dates | | <!-- PASS / FAIL --> | |
| Custom rule: <!-- name --> | | | | |

### Referential Integrity

| Check | Source Column | References | Status | Orphan Count |
|-------|---------------|------------|--------|--------------|
| `customer_id` → `dim_customers` | `fact_orders.customer_id` | `dim_customers.customer_id` | <!-- PASS / FAIL --> | |
| `product_id` → `dim_products` | | | <!-- PASS / FAIL / N-A --> | |

### Distribution / Anomaly Detection

| Metric | Baseline (30-day avg) | Today | Z-Score | Status |
|--------|----------------------|-------|---------|--------|
| Row count | | | | <!-- PASS / WARN --> |
| Average `total_amount` | | | | <!-- PASS / WARN --> |
| Distinct `customer_id` count | | | | <!-- PASS / WARN --> |

---

## Quarantine Report

| Quarantine Reason | Row Count | Partition | Resolution Status |
|-------------------|-----------|-----------|-------------------|
| Duplicate `order_id` | | | <!-- Pending / Resolved / Monitoring --> |
| NULL required column | | | |
| Invalid `order_status` value | | | |

**Total rows quarantined:** <!-- N -->
**Quarantine table:** <!-- `project.raw_orders.orders__quarantine` -->
**Next review date:** <!-- YYYY-MM-DD -->

---

## Root Cause Analysis (for FAIL items)

<!-- For each FAIL, document: -->

### FAIL 1: <!-- Check name -->

**Affected rows:** <!-- N rows, N% of total -->
**Likely cause:** <!-- e.g., upstream schema change, source system bug, pipeline logic error -->
**Evidence:** <!-- SQL query or error log snippet that confirms the cause -->
**Impact:** <!-- What downstream consumers are affected -->
**Resolution:**

- [ ] <!-- Action 1 -->
- [ ] <!-- Action 2 -->

**Owner:** <!-- Team or individual -->
**Target resolution date:** <!-- YYYY-MM-DD -->

---

## Trend Analysis

<!-- Optional: fill in if running recurring DQ reports -->

| Date | PASS | WARN | FAIL | Rows Quarantined | Overall Health |
|------|------|------|------|------------------|----------------|
| | | | | | |
| | | | | | |
| | | | | | |

<!-- Note: if FAIL count is increasing over time, escalate to pipeline owner. -->

---

## Recommendations

### Immediate Actions (blocking)

1. <!-- e.g., Halt mart load until duplicates are resolved -->

### Short-term (within 1 sprint)

1. <!-- e.g., Add `require_partition_filter = TRUE` to the source table -->
2. <!-- e.g., Add referential integrity dbt test for `product_id` -->

### Long-term (within 1 quarter)

1. <!-- e.g., Implement Dataplex DQ scans to replace manual SQL assertions -->
2. <!-- e.g., Add anomaly detection alert to Cloud Monitoring -->

---

## Approval

| Role | Name | Decision | Date |
|------|------|----------|------|
| DQ Owner | | <!-- Approved / Escalating --> | |
| Pipeline Owner | | <!-- Acknowledged --> | |
| On-call | | <!-- Resolved / Monitoring --> | |
