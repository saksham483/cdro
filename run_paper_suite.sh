#!/usr/bin/env bash
# ==============================================================================
# CDRO Research Paper Complete Measurement & Benchmark Execution Suite
# Paper: "Cloud Disaster Recovery Orchestrator (CDRO): An Automated Framework
#         for Application Failure Detection and Recovery"
# Authors: Saksham Dhakad, Jiya, Kuhu Chandna
# ==============================================================================
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

echo "=================================================================="
echo " CDRO Research Paper: Complete Measurement Suite Execution        "
echo "=================================================================="

# Step 1: Run Pytest Measurement Suite
echo ""
echo "[STEP 1/3] Running Full Automated Pytest Suite (44 Tests)..."
"$BASE_DIR/.venv/bin/pytest" -v backend/tests/test_paper_measurements.py

# Step 2: Run Empirical Benchmarks
echo ""
echo "[STEP 2/3] Running Empirical Paper Benchmarks (Table V & Latencies)..."
"$BASE_DIR/.venv/bin/python3" benchmarks/run_paper_experiments.py

# Step 3: Generate Publication Figures
echo ""
echo "[STEP 3/3] Generating High-Resolution (300 DPI) Publication Figures..."
"$BASE_DIR/.venv/bin/python3" benchmarks/generate_paper_plots.py

echo ""
echo "=================================================================="
echo " [SUCCESS] All measurements, benchmarks, and plots generated!"
echo " Results available in:"
echo "   - Markdown Report: benchmarks/results/paper_metrics_report.md"
echo "   - LaTeX Table V:   benchmarks/results/table_v.tex"
echo "   - JSON Dataset:    benchmarks/results/all_results.json"
echo "   - Figures (300DPI): benchmarks/results/figures/"
echo "=================================================================="
