from __future__ import annotations

import math
import os
import shutil
import warnings
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages
from scipy.stats import fisher_exact


warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
OUT = SCRIPT_DIR / "regression_only"
FIG_DIR = OUT / "figures"
TABLE_DIR = OUT / "tables"
DATA_DIR = OUT / "data"
PPT_DIR = OUT / "ppt_ready_materials"
DATA_PATH = Path(os.environ.get("PC_DIAGNOSE_CYTOLOGY_WORKBOOK", ROOT / "private_data" / "cytology_source.xlsx"))

for directory in [OUT, FIG_DIR, TABLE_DIR, DATA_DIR, PPT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


COLUMN_RENAMES = {
    "性别（1-男 2-女）": "性别",
    "症状（0-无 1-有）": "症状",
    "体重下降（0-无 1-10kg以内 2-10kg及以上）": "体重下降",
    "吸烟（1-是 0-否）": "吸烟",
    "饮酒（1-是 0-否）": "饮酒",
    "既往史（0-无 1-有）": "胆胰疾病既往史",
    "胆胰疾病家族史（1-有 0-无）": "胆胰疾病家族史",
    "CEA（0-不高 1-高）": "CEA升高",
    "CA19-9（0-无 1-＜100 2-＞100）": "CA19-9",
    "黄疸（0-无 1-有，34为界）": "黄疸/TBil>34",
    "IgG4（0-不高 1-高）": "IgG4升高",
    "是否有血管包绕": "血管包绕",
    "病灶长径（cm）": "病灶长径(cm)",
    "针（型号，数字越大针越细，22、25较常用）": "穿刺针型号",
    "针数": "穿刺针数",
    "抽吸方式（1-负压 2-负压+湿法）": "抽吸方式",
    "穿刺部位（1-胰头 2-钩突 3-胰颈 4-胰体 5-胰尾 6-其他）": "穿刺/病灶部位",
    "细胞穿刺结果（1-无法诊断 2-良性 3-非典型 4 -neoplastic 5-可疑恶性 6-恶性": "首次细胞学结果",
    "最终诊断（0-非胰腺癌 1-胰腺癌）": "最终诊断",
}

CYTOLOGY_LABELS = {
    1: "无法诊断",
    2: "良性",
    3: "非典型",
    4: "neoplastic",
    5: "可疑恶性",
    6: "恶性",
}

HIGH_MISSING_THRESHOLD = 0.30

MULTIVARIABLE_MODEL_NAME = "统一多因素Logistic回归"
MULTIVARIABLE_TERMS = [
    "年龄每1岁",
    "女性vs男性",
    "有症状vs无症状",
    "体重下降<10kg vs 无",
    "体重下降>=10kg vs 无",
    "吸烟vs不吸烟",
    "饮酒vs不饮酒",
    "胆胰疾病既往史vs无",
    "胆胰疾病家族史vs无",
    "CEA升高vs正常",
    "CA19-9<100 vs 正常",
    "CA19-9>=100 vs 正常",
    "黄疸/TBil>34 vs 无",
    "IgG4升高vs正常",
    "肿大淋巴结vs无",
    "血管包绕vs无",
    "病灶长径每1cm",
    "胰管扩张vs无",
    "胆管扩张vs无",
    "穿刺针型号每增1G",
    "穿刺针数每增加1针",
    "负压+湿法 vs 负压",
    "穿刺部位钩突vs胰头",
    "穿刺部位胰颈vs胰头",
    "穿刺部位胰体vs胰头",
    "穿刺部位胰尾vs胰头",
]


def configure_style() -> font_manager.FontProperties | None:
    sns.set_theme(style="whitegrid", context="talk")
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    selected = None
    for font_path in font_paths:
        path = Path(font_path)
        if path.exists():
            try:
                font_manager.fontManager.addfont(str(path))
                selected = path
                break
            except Exception:
                continue
    if selected:
        prop = font_manager.FontProperties(fname=str(selected))
        plt.rcParams["font.sans-serif"] = [prop.get_name(), "DejaVu Sans"]
    else:
        prop = None
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 130
    plt.rcParams["savefig.dpi"] = 300
    return prop


FONT_PROP = configure_style()


def clean_name(name: object) -> str:
    return COLUMN_RENAMES.get(str(name).strip(), str(name).strip())


def bool_series(series: pd.Series, value: int | float) -> pd.Series:
    return series.eq(value).where(series.notna(), np.nan)


def load_clean_data() -> tuple[pd.DataFrame, dict]:
    raw = pd.read_excel(DATA_PATH, dtype=object)
    raw.columns = [clean_name(c) for c in raw.columns]
    df = raw[~raw["姓名"].astype(str).str.contains("首次穿刺", na=False)].copy()
    for col in df.columns:
        if col not in {"姓名", "ID号"}:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["首次细胞学结果"].isin([1, 2, 3, 4, 5, 6])].copy()
    df["细胞学阳性"] = df["首次细胞学结果"].isin([5, 6]).astype(int)
    df["细胞学结果标签"] = df["首次细胞学结果"].map(CYTOLOGY_LABELS)
    metadata = {
        "source_file": str(DATA_PATH),
        "raw_n": int(len(raw)),
        "valid_n": int(len(df)),
        "positive_n": int(df["细胞学阳性"].sum()),
        "negative_n": int((1 - df["细胞学阳性"]).sum()),
    }
    return df, metadata


def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    features["年龄每1岁"] = df["年龄"]
    features["女性vs男性"] = bool_series(df["性别"], 2)
    features["有症状vs无症状"] = bool_series(df["症状"], 1)
    features["体重下降<10kg vs 无"] = bool_series(df["体重下降"], 1)
    features["体重下降>=10kg vs 无"] = bool_series(df["体重下降"], 2)
    features["吸烟vs不吸烟"] = bool_series(df["吸烟"], 1)
    features["饮酒vs不饮酒"] = bool_series(df["饮酒"], 1)
    features["胆胰疾病既往史vs无"] = bool_series(df["胆胰疾病既往史"], 1)
    features["胆胰疾病家族史vs无"] = bool_series(df["胆胰疾病家族史"], 1)
    features["CEA升高vs正常"] = bool_series(df["CEA升高"], 1)
    features["CA19-9<100 vs 正常"] = bool_series(df["CA19-9"], 1)
    features["CA19-9>=100 vs 正常"] = bool_series(df["CA19-9"], 2)
    features["黄疸/TBil>34 vs 无"] = bool_series(df["黄疸/TBil>34"], 1)
    features["IgG4升高vs正常"] = bool_series(df["IgG4升高"], 1)
    features["肿大淋巴结vs无"] = bool_series(df["肿大淋巴结"], 1)
    features["血管包绕vs无"] = bool_series(df["血管包绕"], 1)
    features["病灶长径每1cm"] = df["病灶长径(cm)"]
    features["胰管扩张vs无"] = bool_series(df["胰管扩张"], 1)
    features["胆管扩张vs无"] = bool_series(df["胆管扩张"], 1)
    features["穿刺针型号每增1G"] = df["穿刺针型号"]
    features["穿刺针数每增加1针"] = df["穿刺针数"]
    features["负压+湿法 vs 负压"] = bool_series(df["抽吸方式"], 2)
    features["穿刺部位钩突vs胰头"] = bool_series(df["穿刺/病灶部位"], 2)
    features["穿刺部位胰颈vs胰头"] = bool_series(df["穿刺/病灶部位"], 3)
    features["穿刺部位胰体vs胰头"] = bool_series(df["穿刺/病灶部位"], 4)
    features["穿刺部位胰尾vs胰头"] = bool_series(df["穿刺/病灶部位"], 5)
    return features.astype(float)


def format_p(p_value: float) -> str:
    if pd.isna(p_value):
        return ""
    if p_value < 0.001:
        return "<0.001"
    return f"{p_value:.3f}"


def format_pct(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.1%}"


def or_ci(beta: float, se: float) -> tuple[float, float, float]:
    return math.exp(beta), math.exp(beta - 1.96 * se), math.exp(beta + 1.96 * se)


def missing_table(features: pd.DataFrame) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "变量": features.columns,
            "可用例数": features.notna().sum().values,
            "缺失例数": features.isna().sum().values,
            "缺失比例": features.isna().mean().values,
        }
    )
    table["处理"] = np.where(
        table["缺失比例"] > HIGH_MISSING_THRESHOLD,
        "剔除正式回归",
        "纳入分析",
    )
    table["说明"] = np.where(
        table["缺失比例"] > HIGH_MISSING_THRESHOLD,
        f"缺失比例>{int(HIGH_MISSING_THRESHOLD * 100)}%，仅作为数据限制说明",
        "单因素按可用样本；多因素按模型变量完整病例",
    )
    return table


def eligible_features(features: pd.DataFrame, miss: pd.DataFrame) -> pd.DataFrame:
    keep = miss.loc[miss["处理"].eq("纳入分析"), "变量"].tolist()
    return features[keep].copy()


def univariate_logistic(y: pd.Series, features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in features.columns:
        d = pd.concat([y.rename("y"), features[name].rename("x")], axis=1).dropna()
        if len(d) == 0 or d["x"].nunique() < 2 or d["y"].nunique() < 2:
            continue
        row = {"变量": name, "N": len(d), "阳性例数": int(d["y"].sum()), "阴性例数": int((1 - d["y"]).sum())}
        try:
            model = sm.Logit(d["y"], sm.add_constant(d["x"], has_constant="add")).fit(disp=False, maxiter=300)
            beta = model.params["x"]
            se = model.bse["x"]
            or_value, low, high = or_ci(beta, se)
            row.update(
                {
                    "OR": or_value,
                    "95%CI下限": low,
                    "95%CI上限": high,
                    "P值": model.pvalues["x"],
                    "OR(95%CI)": f"{or_value:.2f} ({low:.2f}-{high:.2f})",
                    "P值格式": format_p(model.pvalues["x"]),
                    "备注": "",
                }
            )
        except Exception:
            if set(d["x"].dropna().unique()).issubset({0.0, 1.0}):
                tab = pd.crosstab(d["x"], d["y"]).reindex(index=[0.0, 1.0], columns=[0, 1], fill_value=0)
                a = tab.loc[1.0, 1] + 0.5
                b = tab.loc[1.0, 0] + 0.5
                c = tab.loc[0.0, 1] + 0.5
                dd = tab.loc[0.0, 0] + 0.5
                or_value = (a * dd) / (b * c)
                se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / dd)
                low = math.exp(math.log(or_value) - 1.96 * se)
                high = math.exp(math.log(or_value) + 1.96 * se)
                p_value = fisher_exact(tab.to_numpy())[1]
                row.update(
                    {
                        "OR": or_value,
                        "95%CI下限": low,
                        "95%CI上限": high,
                        "P值": p_value,
                        "OR(95%CI)": f"{or_value:.2f} ({low:.2f}-{high:.2f})",
                        "P值格式": format_p(p_value),
                        "备注": "常规Logistic不稳定，使用0.5校正/Fisher检验",
                    }
                )
            else:
                row.update(
                    {
                        "OR": np.nan,
                        "95%CI下限": np.nan,
                        "95%CI上限": np.nan,
                        "P值": np.nan,
                        "OR(95%CI)": "",
                        "P值格式": "",
                        "备注": "模型不稳定，未报告OR",
                    }
                )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("P值", na_position="last")


def fit_multivariable(y: pd.Series, features: pd.DataFrame, variables: list[str], model_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    available = [var for var in variables if var in features.columns]
    d = pd.concat([y.rename("y"), features[available]], axis=1).dropna()
    model = sm.Logit(d["y"], sm.add_constant(d[available], has_constant="add")).fit(disp=False, maxiter=300)
    rows = []
    for term in available:
        beta = model.params[term]
        se = model.bse[term]
        or_value, low, high = or_ci(beta, se)
        rows.append(
            {
                "模型": model_name,
                "变量": term,
                "N": len(d),
                "阳性例数": int(d["y"].sum()),
                "阴性例数": int((1 - d["y"]).sum()),
                "OR": or_value,
                "95%CI下限": low,
                "95%CI上限": high,
                "P值": model.pvalues[term],
                "OR(95%CI)": f"{or_value:.2f} ({low:.2f}-{high:.2f})",
                "P值格式": format_p(model.pvalues[term]),
            }
        )
    model_info = pd.DataFrame(
        [
            {
                "模型": model_name,
                "N": len(d),
                "阳性例数": int(d["y"].sum()),
                "阴性例数": int((1 - d["y"]).sum()),
                "纳入变量": "、".join(available),
                "AIC": model.aic,
            }
        ]
    )
    return pd.DataFrame(rows), model_info


def savefig(name: str) -> None:
    path = FIG_DIR / name
    plt.tight_layout(pad=1.3)
    plt.savefig(path, bbox_inches="tight")
    plt.close()


def plot_forest(table: pd.DataFrame, title: str, filename: str, max_rows: int | None = None) -> None:
    plot_df = table.dropna(subset=["OR", "95%CI下限", "95%CI上限"]).copy()
    if max_rows and len(plot_df) > max_rows:
        plot_df = plot_df.sort_values("P值").head(max_rows)
    plot_df = plot_df.sort_values("OR")
    fig, ax = plt.subplots(figsize=(11.2, max(4.6, 0.48 * len(plot_df) + 1.6)))
    y = np.arange(len(plot_df))
    colors = np.where(plot_df["P值"] < 0.05, "#C74B4B", "#5C89A8")
    ax.errorbar(
        plot_df["OR"],
        y,
        xerr=[plot_df["OR"] - plot_df["95%CI下限"], plot_df["95%CI上限"] - plot_df["OR"]],
        fmt="o",
        color="#333333",
        ecolor="#6B6B6B",
        elinewidth=1.35,
        capsize=3,
        zorder=1,
    )
    ax.scatter(plot_df["OR"], y, s=62, c=colors, edgecolor="#333333", zorder=2)
    ax.axvline(1, linestyle="--", color="#555555", lw=1.25)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["变量"], fontsize=11)
    ax.set_xlabel("OR（对数坐标）")
    ax.set_title(title, fontsize=18, weight="bold", pad=14)
    finite_high = plot_df["95%CI上限"].replace(np.inf, np.nan).dropna()
    finite_low = plot_df["95%CI下限"].replace(0, np.nan).dropna()
    xmax = min(max(finite_high.max() * 1.25, 4), 120) if not finite_high.empty else 10
    xmin = max(finite_low.min() / 1.6, 0.01) if not finite_low.empty else 0.05
    ax.set_xlim(xmin, xmax)
    for i, (_, row) in enumerate(plot_df.iterrows()):
        ax.text(
            xmax / 1.05,
            i,
            f"{row['OR']:.2f} ({row['95%CI下限']:.2f}-{row['95%CI上限']:.2f}), P={format_p(row['P值'])}",
            va="center",
            ha="right",
            fontsize=9.2,
        )
    savefig(filename)


def markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    tmp = df[columns].copy()
    if "缺失比例" in tmp.columns:
        tmp["缺失比例"] = tmp["缺失比例"].map(format_pct)
    return tmp.to_markdown(index=False)


def write_markdown_report(
    metadata: dict,
    miss: pd.DataFrame,
    univ: pd.DataFrame,
    multivariable: pd.DataFrame,
    model_info: pd.DataFrame,
) -> None:
    high_missing = miss[miss["处理"].eq("剔除正式回归")].copy()
    high_missing_text = "无"
    if not high_missing.empty:
        high_missing_text = "；".join(
            f"{row.变量}（缺失{int(row.缺失例数)}/{metadata['valid_n']}，{row.缺失比例:.1%}）"
            for row in high_missing.itertuples()
        )
    top_univ = univ.copy()
    multi_n = int(model_info.loc[0, "N"])
    multi_terms = model_info.loc[0, "纳入变量"]

    report = f"""# 细胞学阳性单因素与统一多因素 Logistic 回归分析报告

## 1. 分析口径

数据来源：本地临床数据。

结局变量：首次细胞学结果是否阳性。`5=可疑恶性` 或 `6=恶性` 定义为阳性；`1=无法诊断`、`2=良性`、`3=非典型`、`4=neoplastic` 定义为阴性/未达阳性。

有效样本共 {metadata['valid_n']} 例，其中细胞学阳性 {metadata['positive_n']} 例，阴性/未达阳性 {metadata['negative_n']} 例。

说明：这是回顾性观察数据，回归结果应表述为“相关因素”或“提示阳性率差异”，不能直接表述为因果意义上的“导致”。

## 2. 缺失变量处理

本次采用保守处理：缺失比例超过 {int(HIGH_MISSING_THRESHOLD * 100)}% 的变量不进入正式单因素或多因素回归；缺失比例较低的变量照常分析，单因素按可用样本，多因素按模型变量完整病例。

本版多因素回归不再拆分为多个模型，也不再使用人为二分阈值。连续变量按连续变量进入模型；原始分类变量用哑变量进入模型，并明确参照组。

被剔除的高缺失变量：{high_missing_text}。

{markdown_table(miss, ['变量', '可用例数', '缺失例数', '缺失比例', '处理'])}

## 3. 单因素 Logistic 回归

单因素回归每次只考察一个变量与细胞学阳性的关系，未调整其他变量。

![单因素森林图](figures/fig_01_univariate_or_forest.png)

{markdown_table(top_univ, ['变量', 'N', '阳性例数', '阴性例数', 'OR(95%CI)', 'P值格式', '备注'])}

单因素结果解读：

- 症状相关变量在本数据中没有显示稳定的细胞学阳性相关性：`有症状vs无症状`、`体重下降<10kg vs 无`、`体重下降>=10kg vs 无` 均未达到 0.05 显著性。
- `穿刺针数每增加1针` 与较低阳性率相关，但更合理的解释是困难病例往往需要追加穿刺，不能解释为穿刺针数增加本身导致阴性。
- CA19-9 原始水平中，`CA19-9>=100 vs 正常` 的 OR>1，但单因素 P 值未达到 0.05；`CA19-9<100 vs 正常` 在单因素中未见阳性率升高。
- 穿刺部位以胰头为参照，其他部位的 OR 用于反映相对胰头部位的阳性率差异。

## 4. 多因素 Logistic 回归

本版只建立一个统一多因素模型。IgG4 因高缺失剔除；其他缺失比例较低或无缺失的变量共同进入同一个模型。完整病例 N={multi_n}。

纳入变量：{multi_terms}。

![统一多因素森林图](figures/fig_02_multivariable_forest_unified.png)

{markdown_table(multivariable, ['变量', 'N', '阳性例数', '阴性例数', 'OR(95%CI)', 'P值格式'])}

## 5. 主要结论

1. 在当前 95 例有效病例中，症状变量本身没有显示出能稳定预测首次细胞学阳性/阴性的统计学证据。
2. 在统一多因素模型中，CA19-9 的两个原始水平相对正常组均提示阳性率更高，其中 `CA19-9>=100 vs 正常` 证据更强。
3. 穿刺针数按连续变量进入模型后 OR 仍小于 1，但未达到 0.05 显著性；该变量高度可能受到适应证偏倚影响，应解释为“困难取材病例往往需要更多针”，不能解释为“多穿针导致阴性”。
4. 穿刺部位、针型号、抽吸方式等取材变量已与其他变量一起进入统一模型，但样本量较小、置信区间较宽，应谨慎解释。
5. IgG4 缺失比例较高，本次已从正式回归中剔除，只作为数据完整性限制说明。
"""
    (OUT / "细胞学阳性单因素与统一多因素回归报告.md").write_text(report, encoding="utf-8")
    (OUT / "细胞学阳性单因素与多因素回归报告.md").write_text(report, encoding="utf-8")
    (PPT_DIR / "PPT汇报要点_仅回归.md").write_text(
        "\n".join(
            [
                "# 细胞学阳性单因素与多因素回归PPT要点",
                "",
                "1. 结局：首次细胞学可疑恶性/恶性=阳性；其余=阴性/未达阳性。",
                f"2. 样本：有效病例{metadata['valid_n']}例，阳性{metadata['positive_n']}例，阴性/未达阳性{metadata['negative_n']}例。",
                "3. 缺失：IgG4缺失比例高，已剔除正式回归；低缺失变量照常按可用样本/完整病例分析。",
                "4. 单因素：症状变量未见稳定关联；穿刺针数每增加1针与较低阳性率相关；CA19-9>=100相对正常组OR>1但未达0.05。",
                "5. 多因素：统一纳入低缺失变量，不再拆分模型组；症状变量调整后仍未显示明确独立关联。",
            ]
        ),
        encoding="utf-8",
    )


def wrap_text(text: str, width: int = 42) -> list[str]:
    lines = []
    for paragraph in str(text).split("\n"):
        paragraph = paragraph.strip()
        while len(paragraph) > width:
            cut = paragraph.rfind("，", 0, width)
            if cut < width * 0.55:
                cut = paragraph.rfind("。", 0, width)
            if cut < width * 0.55:
                cut = width
            lines.append(paragraph[:cut + 1].strip())
            paragraph = paragraph[cut + 1 :].strip()
        if paragraph:
            lines.append(paragraph)
    return lines


def pdf_text_page(pdf: PdfPages, title: str, paragraphs: list[str]) -> None:
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    y = 0.94
    ax.text(0.06, y, title, fontsize=19, weight="bold", color="#1F4E6E", transform=ax.transAxes)
    y -= 0.065
    for paragraph in paragraphs:
        if paragraph == "":
            y -= 0.025
            continue
        for line in wrap_text(paragraph, 43):
            ax.text(0.08, y, line, fontsize=11.2, transform=ax.transAxes, va="top")
            y -= 0.031
        y -= 0.014
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def pdf_image_page(pdf: PdfPages, title: str, image_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.text(0.05, 0.96, title, fontsize=17, weight="bold", color="#1F4E6E", transform=ax.transAxes)
    img = mpimg.imread(image_path)
    ax_img = fig.add_axes([0.05, 0.08, 0.90, 0.84])
    ax_img.imshow(img)
    ax_img.axis("off")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def pdf_table_pages(pdf: PdfPages, title: str, df: pd.DataFrame, columns: list[str], rows_per_page: int = 16) -> None:
    display = df[columns].copy().astype(str)
    for start in range(0, len(display), rows_per_page):
        chunk = display.iloc[start : start + rows_per_page]
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        page_title = title if len(display) <= rows_per_page else f"{title}（{start + 1}-{start + len(chunk)}行）"
        ax.text(0.04, 0.95, page_title, fontsize=16, weight="bold", color="#1F4E6E", transform=ax.transAxes)
        table = ax.table(
            cellText=chunk.values,
            colLabels=columns,
            cellLoc="center",
            colLoc="center",
            loc="upper left",
            bbox=[0.03, 0.07, 0.94, 0.84],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8.5)
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor("#D0D5DA")
            if row == 0:
                cell.set_facecolor("#DCEBF3")
                cell.set_text_props(weight="bold", color="#1F3D52")
            elif row % 2 == 0:
                cell.set_facecolor("#F7FAFC")
            if col in [0, len(columns) - 1]:
                cell.set_text_props(ha="left")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def write_pdf_report(
    metadata: dict,
    miss: pd.DataFrame,
    univ: pd.DataFrame,
    multivariable: pd.DataFrame,
    model_info: pd.DataFrame,
) -> None:
    pdf_path = OUT / "细胞学阳性单因素与统一多因素回归报告.pdf"
    high_missing = miss[miss["处理"].eq("剔除正式回归")]
    high_missing_text = "无"
    if not high_missing.empty:
        high_missing_text = "；".join(
            f"{row.变量}缺失{int(row.缺失例数)}/{metadata['valid_n']}（{row.缺失比例:.1%}）"
            for row in high_missing.itertuples()
        )

    miss_pdf = miss.copy()
    miss_pdf["缺失比例"] = miss_pdf["缺失比例"].map(format_pct)
    multi_n = int(model_info.loc[0, "N"])
    multi_terms = model_info.loc[0, "纳入变量"]

    with PdfPages(pdf_path) as pdf:
        pdf_text_page(
            pdf,
            "细胞学阳性单因素与统一多因素 Logistic 回归分析报告",
            [
                f"数据来源：本地临床数据。有效病例{metadata['valid_n']}例，细胞学阳性{metadata['positive_n']}例，阴性/未达阳性{metadata['negative_n']}例。",
                "结局定义：首次细胞学结果5=可疑恶性或6=恶性定义为阳性；1-4定义为阴性/未达阳性。",
                f"缺失处理：缺失比例超过{int(HIGH_MISSING_THRESHOLD * 100)}%的变量不进入正式回归；低缺失变量正常分析。剔除变量：{high_missing_text}。",
                "多因素模型：不再拆分为多个模型，低缺失变量统一进入一个Logistic回归；连续变量按连续值进入，原始分类变量用哑变量表示。",
                f"统一多因素模型完整病例N={multi_n}。纳入变量：{multi_terms}。",
                "解释口径：本分析为回顾性观察数据，只能说明相关或提示阳性率差异，不能直接证明因果。",
            ],
        )
        pdf_table_pages(pdf, "变量缺失与处理", miss_pdf, ["变量", "可用例数", "缺失例数", "缺失比例", "处理"], rows_per_page=18)
        pdf_image_page(pdf, "单因素 Logistic 回归森林图", FIG_DIR / "fig_01_univariate_or_forest.png")
        pdf_table_pages(pdf, "单因素 Logistic 回归结果", univ, ["变量", "N", "阳性例数", "阴性例数", "OR(95%CI)", "P值格式", "备注"], rows_per_page=14)
        pdf_image_page(pdf, "统一多因素 Logistic 回归森林图", FIG_DIR / "fig_02_multivariable_forest_unified.png")
        pdf_table_pages(pdf, "统一多因素 Logistic 回归结果", multivariable, ["变量", "N", "阳性例数", "阴性例数", "OR(95%CI)", "P值格式"], rows_per_page=14)
        pdf_text_page(
            pdf,
            "结论",
            [
                "1. 症状变量本身，包括有症状、体重下降<10kg、体重下降>=10kg，在当前数据中没有显示稳定的细胞学阳性相关性。",
                "2. 在统一多因素模型中，CA19-9两个原始水平相对正常组均提示阳性率更高，其中CA19-9>=100证据更强。",
                "3. 穿刺针数按连续变量进入模型后OR仍小于1，但未达到0.05显著性；该变量应按困难取材标志谨慎解释。",
                "4. 穿刺部位、针型号、抽吸方式等取材变量已统一纳入模型，但样本量较小、置信区间较宽，应谨慎解释。",
                "5. IgG4缺失比例较高，已从正式回归中剔除，只作为数据完整性限制说明。",
            ],
        )
    shutil.copy2(pdf_path, OUT / "细胞学阳性单因素与多因素回归报告.pdf")


def build_outputs() -> None:
    df, metadata = load_clean_data()
    features = derive_features(df)
    miss = missing_table(features)
    formal_features = eligible_features(features, miss)

    df_out = pd.concat([df, features], axis=1)
    df_out.to_csv(DATA_DIR / "cleaned_cytology_regression_only_2026.csv", index=False)

    univ = univariate_logistic(df["细胞学阳性"], formal_features)
    multivariable, model_info = fit_multivariable(
        df["细胞学阳性"],
        formal_features,
        MULTIVARIABLE_TERMS,
        MULTIVARIABLE_MODEL_NAME,
    )

    miss.to_csv(TABLE_DIR / "table_00_missing_handling.csv", index=False)
    univ.to_csv(TABLE_DIR / "table_01_univariate_logistic.csv", index=False)
    multivariable.to_csv(TABLE_DIR / "table_02_multivariable_unified.csv", index=False)
    model_info.to_csv(TABLE_DIR / "table_03_model_info.csv", index=False)

    with pd.ExcelWriter(OUT / "cytology_regression_only_results_2026.xlsx", engine="openpyxl") as writer:
        miss.to_excel(writer, sheet_name="missing_handling", index=False)
        univ.to_excel(writer, sheet_name="univariate_logistic", index=False)
        multivariable.to_excel(writer, sheet_name="multivar_unified", index=False)
        model_info.to_excel(writer, sheet_name="model_info", index=False)

    plot_forest(univ, "单因素Logistic回归：细胞学阳性相关因素", "fig_01_univariate_or_forest.png", max_rows=18)
    plot_forest(multivariable, "统一多因素Logistic回归：所有低缺失变量", "fig_02_multivariable_forest_unified.png")

    write_markdown_report(metadata, miss, univ, multivariable, model_info)
    write_pdf_report(metadata, miss, univ, multivariable, model_info)

    for png in FIG_DIR.glob("*.png"):
        shutil.copy2(png, OUT / png.name)

    print(f"Generated regression-only outputs in: {OUT}")
    print(f"PDF: {OUT / '细胞学阳性单因素与统一多因素回归报告.pdf'}")


if __name__ == "__main__":
    build_outputs()
