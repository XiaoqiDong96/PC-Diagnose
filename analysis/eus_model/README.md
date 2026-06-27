# 胰腺占位首次穿刺未确诊患者分类器分析

本文件夹包含围绕“首次穿刺未确诊”患者建立胰腺癌风险预测模型的可复现源码。

## 主要文件

- `EUS_first_puncture_undiagnosed_classifier.ipynb`：清除输出后的 Notebook 骨架，保留代码与文字结构。
- `analysis_pipeline.py`：生成 Notebook 与分析结果的主脚本。

## 数据说明

原始临床数据、清洗后患者数据和生成结果不上传 GitHub。

## 运行

在项目根目录运行：

```bash
python analysis/eus_model/analysis_pipeline.py
```

生成的 `data/`、`tables/`、`figures/`、`ppt_ready_figures/`、`ppt_ready_materials/` 等目录会被 `.gitignore` 排除。
