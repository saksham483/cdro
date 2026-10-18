#!/usr/bin/env python3
"""
Publication Figure Generator for CDRO Research Paper
Generates high-resolution (300 DPI) figures for IEEE/ACM paper submission.
"""

import os
import json
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
FIGS_DIR = os.path.join(RESULTS_DIR, "figures")
os.makedirs(FIGS_DIR, exist_ok=True)

# Set publication style
plt.rcParams.update({
    "font.size": 10,
    "font.family": "serif",
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 13,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight"
})

def plot_rto_breakdown(data):
    decomp = data["rto_decomposition"]
    phases = [
        "Lock",
        "Hash Check",
        "Extraction",
        "DB Restore",
        "State Reset",
        "Verification"
    ]
    latencies = [
        decomp["lock_acquisition"]["mean_ms"],
        decomp["candidate_search_and_hash"]["mean_ms"],
        decomp["workspace_extraction"]["mean_ms"],
        decomp["database_restoration"]["mean_ms"],
        decomp["failure_state_reset"]["mean_ms"],
        decomp["post_recovery_verification"]["mean_ms"]
    ]
    errors = [
        decomp["lock_acquisition"]["std_ms"],
        decomp["candidate_search_and_hash"]["std_ms"],
        decomp["workspace_extraction"]["std_ms"],
        decomp["database_restoration"]["std_ms"],
        decomp["failure_state_reset"]["std_ms"],
        decomp["post_recovery_verification"]["std_ms"]
    ]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    colors = ["#4c72b0", "#55a868", "#c44e52", "#8172b3", "#ccb974", "#64b5cd"]
    bars = ax.bar(phases, latencies, yerr=errors, capsize=4, color=colors, edgecolor="black", linewidth=0.8)

    ax.set_ylabel("Latency (milliseconds)")
    ax.set_title("Fig. 3: Recovery Sub-Phase Latency Decomposition", pad=12)
    ax.grid(axis="y", linestyle="--", alpha=0.6)

    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{h:.1f} ms",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    outpath = os.path.join(FIGS_DIR, "fig_rto_breakdown.png")
    plt.savefig(outpath)
    plt.close()
    print(f"Generated: {outpath}")

def plot_sha256_scaling(data):
    scaling = data["checksum_scaling"]["scaling_data"]
    sizes_mb = [r["size_mb"] for r in scaling]
    latencies_ms = [r["hashing_time_ms"] for r in scaling]

    fig, ax1 = plt.subplots(figsize=(6, 3.5))

    # Scatter & Regression line
    ax1.plot(sizes_mb, latencies_ms, "o-", color="#1f77b4", label="Empirical Hash Latency (ms)", linewidth=2, markersize=6)
    z = np.polyfit(sizes_mb, latencies_ms, 1)
    p = np.poly1d(z)
    ax1.plot(sizes_mb, p(sizes_mb), "--", color="#d62728", label=f"Linear Fit O(m) ($R^2={data['checksum_scaling']['r_squared']}$)")

    ax1.set_xlabel("Backup Payload Size (MB)")
    ax1.set_ylabel("Verification Time (ms)", color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax1.set_title("Fig. 4: SHA-256 Checksum Computation Complexity vs. Size", pad=12)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left")

    plt.tight_layout()
    outpath = os.path.join(FIGS_DIR, "fig_sha256_scaling.png")
    plt.savefig(outpath)
    plt.close()
    print(f"Generated: {outpath}")

def plot_fallback_penalty(data):
    fallback = data["fallback_penalty"]
    corrupted_counts = [r["corrupted_candidates_skipped"] for r in fallback]
    search_latencies = [r["search_and_verification_latency_ms"] for r in fallback]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(corrupted_counts, search_latencies, "s-", color="#2ca02c", linewidth=2, markersize=7)

    ax.set_xlabel("Number of Corrupted Candidates Skipped (k)")
    ax.set_ylabel("Search & Verification Latency (ms)")
    ax.set_title("Fig. 5: Fallback Search Latency vs. Corrupted Backups $O(n)$", pad=12)
    ax.set_xticks(corrupted_counts)
    ax.grid(True, linestyle="--", alpha=0.5)

    for i, txt in enumerate(search_latencies):
        ax.annotate(f"{txt:.2f} ms",
                    xy=(corrupted_counts[i], txt),
                    xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=8)

    plt.tight_layout()
    outpath = os.path.join(FIGS_DIR, "fig_fallback_penalty.png")
    plt.savefig(outpath)
    plt.close()
    print(f"Generated: {outpath}")

def plot_mttd_sensitivity(data):
    mttd_data = data["detection_sensitivity"]
    intervals = [r["probe_interval_seconds"] for r in mttd_data]
    theoretical = [r["theoretical_mttd_seconds"] for r in mttd_data]
    empirical = [r["empirical_mttd_seconds"] for r in mttd_data]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(intervals, theoretical, "o--", color="#ff7f0e", label="Theoretical MTTD", linewidth=1.8)
    ax.plot(intervals, empirical, "s-", color="#1f77b4", label=r"Empirical MTTD ($\pm 0.4 \Delta t$)", linewidth=2)

    ax.set_xlabel(r"Probe Interval $\Delta t$ (seconds)")
    ax.set_ylabel("Mean Time to Detect (seconds)")
    ax.set_title(r"Fig. 6: Failure Detection Sensitivity ($\tau = 3$ Probes)", pad=12)
    ax.set_xticks(intervals)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend()

    plt.tight_layout()
    outpath = os.path.join(FIGS_DIR, "fig_mttd_sensitivity.png")
    plt.savefig(outpath)
    plt.close()
    print(f"Generated: {outpath}")

def plot_data_consistency(data):
    if "data_consistency" not in data:
        return
    dc = data["data_consistency"]
    entities = ["Users", "Products"]
    before = [dc["users_before_count"], dc["products_before_count"]]
    after = [dc["users_after_count"], dc["products_after_count"]]

    x = np.arange(len(entities))
    width = 0.35

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    rects1 = ax.bar(x - width/2, before, width, label="Pre-Failure Database", color="#4c72b0", edgecolor="black")
    rects2 = ax.bar(x + width/2, after, width, label="Restored Database", color="#55a868", edgecolor="black")

    ax.set_ylabel("Entity Row Count")
    ax.set_title("Fig. 7: Post-Recovery Data Consistency & Preservation (100%)", pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(entities)
    ax.set_ylim(0, max(before + after) + 2)
    ax.legend(loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for rect in list(rects1) + list(rects2):
        height = rect.get_height()
        ax.annotate(f"{int(height)}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    outpath = os.path.join(FIGS_DIR, "fig_data_consistency.png")
    plt.savefig(outpath)
    plt.close()
    print(f"Generated: {outpath}")

def plot_rpo_drift(data):
    if "rpo_drift" not in data:
        return
    rpo = data["rpo_drift"]
    scenarios = ["Corrupted B1\n(Rejected)", "Fallback B2\n(Restored)"]
    ages = [rpo["latest_corrupted_backup_age_seconds"], rpo["fallback_valid_backup_age_seconds"]]
    colors = ["#c44e52", "#55a868"]

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    bars = ax.bar(scenarios, ages, color=colors, edgecolor="black", width=0.45)

    ax.set_ylabel("Data Age / RPO (seconds)")
    ax.set_title("Fig. 8: RPO Drift Gap under Fallback Mechanism", pad=12)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}s ({h/60.0:.1f} min)",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    outpath = os.path.join(FIGS_DIR, "fig_rpo_drift.png")
    plt.savefig(outpath)
    plt.close()
    print(f"Generated: {outpath}")

def main():
    json_path = os.path.join(RESULTS_DIR, "all_results.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found. Run run_paper_experiments.py first.")
        return

    with open(json_path, "r") as f:
        data = json.load(f)

    plot_rto_breakdown(data)
    plot_sha256_scaling(data)
    plot_fallback_penalty(data)
    plot_mttd_sensitivity(data)
    plot_data_consistency(data)
    plot_rpo_drift(data)
    print("\nAll publication figures successfully created!")

if __name__ == "__main__":
    main()
