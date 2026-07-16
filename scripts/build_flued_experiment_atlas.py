"""Build the public FLUED experiment atlas from local, non-public archives.

The generated JSON deliberately contains derived curves and key summaries only.
It never copies checkpoints, raw corpora, or unredacted machine paths to the site.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


SITE = Path(r"W:\Aletheion\website")
REPO = Path(r"E:\projects\FLUED\FLUED")
V1 = Path(r"L:\FLUED_archive\migrated_from_K_20260712\E_checkpoints")
V34 = Path(r"L:\FLUED_archive\v34_attribution_matrices_20260716")
OUT = SITE / "public" / "flued-experiment-atlas.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "step" in row:
            rows[int(row["step"])] = row
    return [rows[key] for key in sorted(rows)]


def num(row, *keys):
    for key in keys:
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def normalize(rows, mapping):
    points = []
    for row in rows:
        point = {"step": int(row["step"])}
        for name, candidates in mapping.items():
            value = num(row, *candidates)
            if value is not None:
                point[name] = value
        points.append(point)
    return points


def final(points):
    return points[-1] if points else {}


def curve(run_id, family, label, protocol, evidence, points, note, *, historical=False):
    return {
        "id": run_id,
        "family": family,
        "label": label,
        "protocol": protocol,
        "evidence": evidence,
        "historical": historical,
        "note": note,
        "pointCount": len(points),
        "final": final(points),
        "points": points,
    }


def main():
    curves = []
    rows = []

    # v1 E1: 200-step resampled source. It is published as historical only.
    v1 = read_json(V1 / "e1_v5_paper.json")["records"]
    v1_points = normalize(v1, {
        "loss": ("loss",),
        "reconstruction": ("recon_acc",),
        "latent_per_byte": ("soft_mn",),
        "boundary_std": ("bp_std",),
    })
    curves.append(curve(
        "v1-e1v5", "v1", "E1v5 50K", "历史 200-step 重采样；最后 14.8K 使用 v5e 配置", "historical",
        v1_points, "显示最小可逆软分段假设可收敛；中途含超参数搜索，不与 v2/v3 横比。", historical=True,
    ))
    rows.extend([
        {"version":"v0.4", "stage":"设计", "experiment":"初始实验计划", "steps":"-", "metric":"byte-to-latent 自编码问题定义", "finding":"建立软切分、近似逆译码与边界可学习性的最小假设。", "evidence":"history", "comparable":False},
        {"version":"v1", "stage":"E1", "experiment":"E1v5 50K", "steps":"50K", "metric":"recon_acc 0.99999；m/n 0.378；bp_std 0.443", "finding":"可微 byte boundary 和高保真逆译码可稳定出现。", "evidence":"historical", "comparable":False},
        {"version":"v1", "stage":"E2", "experiment":"CPU reconstruction", "steps":"FLUED 50K / BPE、BLT 40K", "metric":"FLUED byte PPL 1.39；BLT byte PPL 1.13；BPE token PPL 1.21", "finding":"重建指标的 label space 不同，BPE token-level CE 不能与 byte-level 直接比较。", "evidence":"historical", "comparable":False},
        {"version":"v1", "stage":"E3", "experiment":"历史 downstream", "steps":"20K", "metric":"FLUED 1.2114 BPB；BPE 1.4786；BLT 2.6371", "finding":"最早强阳性信号，但 fixed-token / 20K 口径已被 v2 D1 替代。", "evidence":"history-only", "comparable":False},
    ])

    # v2 seed, hyperparameter and fair D1 summaries.
    v2 = read_json(REPO / "results" / "v2" / "results_summary.json")
    for seed in v2["v2_a_class"]["results"]:
        rows.append({"version":"v2", "stage":"A-class", "experiment":f"seed={seed['seed']}", "steps":"50K", "metric":f"eval acc {seed['eval_acc']:.4f}；m/n {seed['m_n']:.3f}；bp_std {seed['bp_std']:.3f}", "finding":"三种子稳定重建与类型相关边界分化。", "evidence":"high", "comparable":True})
    for item in v2["ablation_denoise"]["results"]:
        rows.append({"version":"v2", "stage":"AB2", "experiment":f"denoise_prob={item['denoise_prob']}", "steps":"30K/50K", "metric":f"eval acc {item['eval_acc']:.4f}；m/n {item['m_n']:.3f}", "finding":"去噪越高，压缩更弱；重建仍接近饱和。", "evidence":"high", "comparable":True})
    for item in v2["ablation_compression_weight_03"]["results"]:
        metric = item["status"] if item["eval_acc"] is None else f"acc {item['eval_acc']:.4f}；m/n {item['m_n']:.3f}"
        rows.append({"version":"v2", "stage":"AB1", "experiment":f"w=.30, target={item['target_compression']:.2f}", "steps":"30K", "metric":metric, "finding":"固定压缩压力存在稳定区和 boundary-head 发散区。", "evidence":"high", "comparable":True})
    for item in v2["d1_downstream_2048byte_100k"]["results"]:
        rows.append({"version":"v2", "stage":"D1", "experiment":item["model"], "steps":"100K", "metric":f"BPB {item['bpb']:.4f}；KV/1KB {item['kv_per_1kb']:.1f}；{item['time_min']:.1f} min", "finding":"统一 2048 原始 byte 口径。FLUED 稳定但落后 BPE；BLT 为弱复现，不代表原论文。", "evidence":"high", "comparable":True})

    # Existing v2 curve payload is already an audit-ready derivative of raw logs.
    legacy_curves = read_json(SITE / "public" / "flued-training-curves.json")
    for group_id, group_label in legacy_curves.get("groups", {}).items():
        for run in (item for item in legacy_curves.get("runs", []) if item.get("group") == group_id):
            points = []
            for point in run.get("points", []):
                normalized = {"step": int(point["step"])}
                for source, target in (("loss", "loss"), ("recon_acc", "reconstruction"), ("soft_mn", "latent_per_byte"), ("bp_std", "boundary_std")):
                    if isinstance(point.get(source), (int, float)):
                        normalized[target] = point[source]
                points.append(normalized)
            if points:
                curves.append(curve(
                    f"v2-{group_id}-{run['id']}", "v2", run["label"], group_label,
                    "high", points, run.get("note", "v2 原始训练日志的公开导出。"),
                ))

    # v3.4: all 17 historical 5K ablations, four 20K rate runs, progressive-memory pair, and newest 40K boundary matrix.
    ablation = REPO / "results" / "v3.4" / "5k_ablation" / "logs"
    for path in sorted(ablation.glob("*.jsonl")):
        points = normalize(read_jsonl(path), {
            "loss": ("loss", "total_loss"), "reconstruction": ("identity_acc", "recon_acc"),
            "completion": ("completion_mask_acc",), "latent_per_byte": ("actual_backbone_units_per_byte",),
        })
        curves.append(curve(f"v34-5k-{path.stem}", "v3.4 5K", path.stem, "37.3M FLUED + 4.8M probe backbone；512 bytes；seed 42", "historical", points, "迁移前候选筛选；全局路径纠偏后不可作为最终组件结论。", historical=True))
    with (REPO / "results" / "v3.4" / "5k_ablation" / "analysis" / "curve_summary.csv").open(encoding="utf-8-sig") as f:
        for item in csv.DictReader(f):
            rows.append({"version":"v3.4", "stage":"5K 候选筛选", "experiment":item["run"], "steps":"5K", "metric":f"recon {float(item['eval_identity_acc']):.3f}；completion {float(item['eval_completion_mask_acc']):.3f}；latent/byte {float(item['eval_actual_backbone_units_per_byte']):.3f}", "finding":"历史候选，不作为迁移后最终默认。", "evidence":"historical", "comparable":False})

    rate_dir = REPO / "results" / "v3.4" / "20k_rate_comparison" / "logs"
    for path in sorted(rate_dir.glob("*.jsonl")):
        points = normalize(read_jsonl(path), {"reconstruction": ("identity_acc",), "completion": ("completion_mask_acc",), "latent_per_byte": ("actual_backbone_units_per_byte",)})
        curves.append(curve(f"v34-rate-{path.stem}", "v3.4 20K rate", path.stem, "37.3M FLUED + 4.8M probe backbone；512 bytes；seed 42", "controlled", points, "同配置 20K 课程和编码率比较；结果随后受全局路径纠偏限制。", historical=True))
    with (REPO / "results" / "v3.4" / "20k_rate_comparison" / "analysis" / "curve_summary.csv").open(encoding="utf-8-sig") as f:
        for item in csv.DictReader(f):
            rows.append({"version":"v3.4", "stage":"20K coding-rate", "experiment":item["run"], "steps":"20K", "metric":f"recon {float(item['eval_identity_acc']):.3f}；completion {float(item['eval_completion_mask_acc']):.3f}；latent/byte {float(item['eval_actual_backbone_units_per_byte']):.3f}", "finding":"课程和边际编码率候选的同预算比较。", "evidence":"controlled", "comparable":True})

    progressive = REPO / "results" / "v3.4" / "progressive_memory_20k" / "logs"
    for path in sorted(progressive.glob("*.jsonl")):
        points = normalize(read_jsonl(path), {"reconstruction": ("identity_acc",), "completion": ("completion_mask_acc",), "latent_per_byte": ("actual_backbone_units_per_byte",)})
        curves.append(curve(f"v34-memory-{path.stem}", "v3.4 20K memory", path.stem, "同种子 progressive memory；512 bytes", "historical", points, "早期 memory 正负结论已受位置和执行路径纠偏影响，保留为研究过程。", historical=True))

    latest_configs = [
        ("S0 1K transition", V34 / "boundary_schedule_40k" / "s0_double_timebase_transition_1k" / "train_log.jsonl"),
        ("S1 500-step transition", V34 / "boundary_schedule_40k" / "s1_double_timebase_short_transition_500" / "train_log.jsonl"),
    ]
    for label, path in latest_configs:
        points = normalize(read_jsonl(path), {"reconstruction": ("identity_acc",), "completion": ("completion_mask_acc",), "latent_per_byte": ("actual_backbone_units_per_byte",), "grad_norm": ("grad_norm", "total_grad_norm")})
        curves.append(curve(f"v34-latest-{label[:2].lower()}", "v3.4 40K attribution", label, "35.9M FLUED + 4.9M probe backbone；512 bytes；seed 42", "controlled", points, "最新长程边界矩阵。说明容量塌缩和动态边界梯度冲击是两个相继的故障。"))
    rows.extend([
        {"version":"v3.2.1", "stage":"strict masked-source", "experiment":"byte baseline", "steps":"15K", "metric":"mask_acc 0.1440；byte CE 3.3782", "finding":"严格输入侧 mask 的 byte 基线。", "evidence":"high", "comparable":True},
        {"version":"v3.2.1", "stage":"strict masked-source", "experiment":"latent no-memory", "steps":"15K", "metric":"mask_acc 0.1898；delta +0.0458；byte CE 3.1424", "finding":"当前最干净的主干友好度正证据。", "evidence":"high", "comparable":True},
        {"version":"v3.2.1", "stage":"strict masked-source", "experiment":"latent memory", "steps":"15K", "metric":"mask_acc 0.1897；delta +0.0457；byte CE 3.1473", "finding":"memory 不稳定超过 no-memory。", "evidence":"high", "comparable":True},
        {"version":"v3.4", "stage":"40K 边界归因", "experiment":"S0: 1K transition", "steps":"40K", "metric":"recon 0.1842；completion 0.1182；PPL 42.245；latent/byte 0.201", "finding":"延长训练未恢复动态阶段，排除简单欠训练。", "evidence":"controlled", "comparable":True},
        {"version":"v3.4", "stage":"40K 边界归因", "experiment":"S1: 500 transition", "steps":"40K", "metric":"recon 0.2176；completion 0.1214；PPL 41.663；latent/byte 0.150", "finding":"缩短过渡略好，但不解决 hard emit 先行容量塌缩。", "evidence":"controlled", "comparable":True},
        {"version":"v3.4", "stage":"20K memory usage", "experiment":"no-memory / w=0 / w=.02 / w=.05", "steps":"20K", "metric":"w=.05: recon 0.2074；completion 0.1141；PPL 43.488；latent/byte 0.191", "finding":"w=.05 是单种子候选 Pareto 点，不等于 memory 已形成有序语义序列。", "evidence":"controlled", "comparable":True},
    ])

    payload = {
        "meta": {
            "title": "FLUED Experiment Atlas",
            "generated": "2026-07-16",
            "curvePolicy": "每个可用日志点均保留；前端只作视觉平滑，不抽样、不补点。",
            "disclosure": "公开站点仅展示派生曲线和关键指标。checkpoint、语料、原始机器路径不公开。",
            "repository": "https://github.com/wdd9700/FLUED/tree/copilot/implement-stage-a-experiments",
        },
        "rows": rows,
        "curves": curves,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024 / 1024:.2f} MiB; {len(rows)} rows; {len(curves)} curves)")


if __name__ == "__main__":
    main()
