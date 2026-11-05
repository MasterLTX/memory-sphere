# 更新日志

**简体中文** · [English](CHANGELOG.md)

本文件记录这个项目所有值得注意的变更。
格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)；
版本号遵循 [语义化版本](https://semver.org/)。

## 未发布

## [1.0.1] — 2026-11-05

### 修复

- **首屏动画绕错了轴。** 原来的渲染矩阵是
  `M = rmat_x(radians(72)) @ rmat_y(angle)`。因为 `Rx(t)` 会把自转轴 `ŷ`
  送到 `(0, cos t, sin t)`，取这个角度时相当于把**转轴的 95% 放到了 +z 方向——也就是视线方向**，
  于是星球是在*画面内*像转盘子一样旋转，而不是像行星那样自转。
  现在改用 `rmat_x(radians(-18))`：转轴 95% 保持在竖直方向，倾斜角也与
  `render_sphere.py`、`render_frames.py` 既有的静态视角一致，
  所以项目产出的每一张图里极区都朝同一侧。
- 注释和数值此前是对不上的：注释写的是"tilted 18 deg"，代码传的却是 72
  （等于 90 − 18，多算了一道）。
- `README.md` 链接指向 `docs/formulas.md`，而这个文件在仓库里从来不存在。
  现在改指向 `sphere/pipeline/build_sphere.py`——算式真正待的地方。

### 新增

- `scripts/check_hero_spin.py`——用**像素判据**判断首屏 GIF 到底是绕竖直轴自转
  还是在画面内旋转：把相邻帧分别拟合"绕中心旋转"和"水平平移"两个模型再比较残差。
  发生回归时退出码为 1，可以直接卡住发布。
- `README.zh-CN.md` 与 `CHANGELOG.zh-CN.md`——完整简体中文版，
  两个英文文件顶部都有语言切换入口。
- `scripts/check_bilingual_sync.py`——机器检查两个语言版本有没有漂移：
  比对标题结构、代码块、链接目标、数字字面量、表格形状和篇幅比例，
  任何一项对不上就退出码 1。
- `CHANGELOG.md`（本文件）。

### 实测

对 `examples/rotating.gif` 的相邻帧做残差拟合
（平移残差更低 + 竖直漂移接近零 = 行星自转）：

| 版本 | 平移 / 旋转 | 拟合出的运动 | 竖直漂移 |
|---|---|---|---|
| 1.0.0 | 1.463 | 绕中心 +9.09 度/帧（36 帧转满一圈） | 0.750 |
| 1.0.1 | 0.456 | dx +22.1 像素/帧，dy −0.3 像素 | 0.012 |

复现：`python scripts/check_hero_spin.py examples/rotating.gif`

## [1.0.0] — 2026-11-05

首次公开发布。

### 新增

- 管线：PCA → 1,024 个等面积球面锚点 → 密度 / PageRank / 实体数 / 新近度 / 类型
  聚合成高度场 → 位移二十面体球。
- `python -m sphere demo`——合成 3,000 条假记忆，让整条管线在没有数据库、
  没有 API key、也不联网的情况下跑通。
- 可交互的演示页，带 25 帧时间滑块、六种高度场视图和等高线。
- 脱敏的输入契约（`embeddings.tsv`、`links.tsv`、`ent_count.tsv`、`models.tsv`），
  以及 `adapters/` 下只读的 Hindsight 导出器。
- GitHub Pages 在线演示、MIT 许可、第三方声明。

### 已知问题

- 仓库里提交的 `examples/rotating.gif` 是绕视线轴旋转（转盘子），而不是绕竖直轴。
  因此这个 tag 的源码压缩包里带着那张 GIF。已在 1.0.1 修复；
  该 tag 有意保持原样不动。