"""Build the public FLUED experiment atlas from local, non-public archives.

The generated JSON deliberately contains derived curves and key summaries only.
It never copies checkpoints, raw corpora, or unredacted machine paths to the site.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path


# Local data roots are ops-only configuration supplied via environment variables
# (never commit absolute machine paths):
#   FLUED_SITE     -> this website repo root (default: parent of this script)
#   FLUED_REPO     -> local FLUED research repo checkout
#   FLUED_ARCHIVE  -> local experiment archive root (e.g. <drive>:/FLUED_archive)
SITE = Path(os.environ.get("FLUED_SITE", Path(__file__).resolve().parents[1]))
REPO = Path(os.environ["FLUED_REPO"])
_ARCHIVE = Path(os.environ["FLUED_ARCHIVE"])
V1 = _ARCHIVE / "migrated_from_K_20260712" / "E_checkpoints"
V34 = _ARCHIVE / "v34_attribution_matrices_20260716"
V36_S0 = _ARCHIVE / "v36_s0_vs_e2e_20260727"
V36_ATTR = _ARCHIVE / "v36_attribution_matrix_20260731"
V36_GRPO = _ARCHIVE / "s05_grpo_r4_2k_20260802"
V36_S07 = _ARCHIVE / "s07_perchunk_20k_20260802"
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
    # Last available value per key (some logs omit metrics in their final rows).
    out = {}
    for point in reversed(points):
        for key, value in point.items():
            if key not in out:
                out[key] = value
    return out


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

    # v3.6 (KDA generation): S0-vs-E2E pair, attribution matrix, GRPO boundary arms, per-chunk readout.
    # Metric mapping into the shared schema: reconstruction=direct_acc (task 1),
    # completion=backbone_masked_acc (task 2 main protocol), backbone_acc=unmasked full-position acc,
    # chunks=chunks_per_sample. All runs are single seed=42, corpus_v3, 512-byte prompts.
    V36_METRICS = {
        "reconstruction": ("direct_acc",),
        "completion": ("backbone_masked_acc",),
        "backbone_acc": ("backbone_acc",),
        "loss": ("loss",),
        "chunks": ("chunks_per_sample",),
    }
    v36_curve_specs = [
        ("v36-s0e2e", "v3.6 S0 vs E2E", V36_S0, [
            ("arm_a_s0", "arm_a_s0 · 组件预训主基线", "组件预训（S0 segmentor 冻结）主基线：masked 0.149 @ readout 包 k=1（1,536 标量）。"),
            ("arm_b_e2e", "arm_b_e2e · 端到端对照", "端到端对照：masked 0.124，过 12K 后退化；组件预训 +5.8pp 判死端到端路线。"),
        ]),
        ("v36-attr", "v3.6 归因矩阵", V36_ATTR, [
            ("b0_uniform_1x_k1", "B0 · uniform 1x k=1 (384 标量)", "uniform 边界 + 1x KDA：容量下限参照。"),
            ("b1_uniform_4x_k1", "B1 · uniform 4x k=1 (1,536 标量)", "uniform 边界 + 4x KDA：与 arm_a_s0 同容量同率，差 +4.4pp 全部来自 S0 动态边界。"),
            ("k4_s0_4x_rerun", "k4 · S0 4x (6,144 标量)", "S0 边界 + k=4 readout：与 k=1 无显著差异。"),
            ("k16_s0_4x", "k16 · S0 4x (24,576 标量)", "S0 边界 + k=16 readout：k 继续加大仍无增益——容量与 k 均为零效应。"),
        ]),
        ("v36-grpo", "v3.6 S0.5 GRPO", V36_GRPO, [
            ("grpo_arm", "grpo_arm · R4 边界优化", "GRPO R4：约束走可微直接损失 E[count]=Σcut_prob，hard 停点 24.3 段 ≈ 用户手标 21B；质量与控制臂打平——GRPO 当前价值是选粒度。"),
            ("control_arm", "control_arm · 控制臂", "同预算控制臂：chunks 17.6（S0 教师粒度），masked 0.149。"),
        ]),
        ("v36-s07", "v3.6 S0.7 逐段条件化", V36_S07, [
            (".", "per_chunk_readout · 非默认口径", "逐段条件化：unmasked 0.351 / PPL 12.1 证明检索瓶颈可解；masked 0.141 未过预注册线。canonical 维持 v36.1，此臂非默认。"),
        ]),
    ]
    for family_id, family_label, base, arms in v36_curve_specs:
        for arm_dir, label, note in arms:
            points = normalize(read_jsonl(base / arm_dir / "train_log.jsonl"), V36_METRICS)
            curves.append(curve(f"{family_id}-{arm_dir.replace('.', 'perchunk')}", family_label, label, "44.7M FLUED v3.6；512 bytes；seed 42；corpus_v3", "controlled", points, note))

    rows.extend([
        {"version":"v3.6", "stage":"S0 vs E2E", "experiment":"arm_a_s0 组件预训主基线", "steps":"20K", "metric":"masked 0.1485；direct 0.1891；unmasked 0.1907；PPL 34.2", "finding":"当前主基线：整条 prompt = 1 个 readout 包（1,536 标量）。", "evidence":"controlled", "comparable":True},
        {"version":"v3.6", "stage":"S0 vs E2E", "experiment":"arm_b_e2e 端到端对照", "steps":"20K", "metric":"masked 0.1243；direct 0.1305；过 12K 退化", "finding":"组件预训 +5.8pp，端到端路线判死。", "evidence":"controlled", "comparable":True},
        {"version":"v3.6", "stage":"归因矩阵", "experiment":"B0 uniform 1x k=1", "steps":"20K", "metric":"masked 0.1272 @ 384 标量", "finding":"uniform 边界容量下限参照。", "evidence":"controlled", "comparable":True},
        {"version":"v3.6", "stage":"归因矩阵", "experiment":"B1 uniform 4x k=1", "steps":"20K", "metric":"masked 0.1293 @ 1,536 标量", "finding":"与 arm_a_s0 同率同容量：+4.4pp 增益全部来自 S0 动态边界。", "evidence":"controlled", "comparable":True},
        {"version":"v3.6", "stage":"归因矩阵", "experiment":"k4 / k16（S0 4x）", "steps":"20K", "metric":"masked 0.1463 @ 6,144；0.1509 @ 24,576 标量", "finding":"readout 数量 k 无显著差异；容量零效应复核。", "evidence":"controlled", "comparable":True},
        {"version":"v3.6", "stage":"S0.5 GRPO", "experiment":"grpo_arm R4", "steps":"2K（自 3K 基线续训）", "metric":"masked 0.1477；chunks 24.3（hard 停点）", "finding":"边界裁决成功：24.3 段 ≈ 用户手标 21B；GRPO 当前价值=选粒度非提质量。", "evidence":"controlled", "comparable":True},
        {"version":"v3.6", "stage":"S0.5 GRPO", "experiment":"control_arm 控制臂", "steps":"2K", "metric":"masked 0.1492；chunks 17.6", "finding":"质量口径与 R4 打平，差异只在切分粒度。", "evidence":"controlled", "comparable":True},
        {"version":"v3.6", "stage":"S0.7 逐段条件化", "experiment":"per_chunk_readout（非默认）", "steps":"20K", "metric":"unmasked 0.3507；PPL 12.12；masked 0.1413", "finding":"检索瓶颈可解、路线活；masked 未过预注册线，canonical 维持 v36.1。", "evidence":"controlled", "comparable":False},
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
