# v1.2 交接（云层 + 参数面板）

写于 2026-11-06 10:56，因为当前会话体积已达 9.46 M 字符，超过昨天 413 挂掉时的
5.72 M，随时可能断。读这一份就能接上，不必翻对话。

> **同日更新**：云的观感已定稿（第五节整节重写），点精灵方案已删除，门禁已补（第七节）。
> 二/五/七节反映的是 `eaaa167` 之后的状态。

---

## 一、当前状态

| 项 | 状态 |
|---|---|
| 仓库 | `D:\memory-sphere`，GitHub `MasterLTX/memory-sphere` |
| 已发布版本 | **v1.1.0**（tag 已推，Release 已发，Pages 已上线） |
| 工作分支 | `main`，最新 commit `eaaa167`（云壳 + 面板 + 门禁，**未推送**） |
| 数据源 | **当前是真实数据**（10,790 条 × 1024 维 + 120k links），demo 备份在 `data/input_demo/` |

## 二、v1.2 做到哪了

**已完成并提交**：
- `sphere/pipeline/build_cloud.py` —— 云场（reach 定义，双尺度平滑，分块 kNN）
- `sphere/pipeline/gen_web_data.py` —— 导出 `DATA.cloud.{big,small}`
- `template_time.html` —— 13 个滑块的参数面板（URL + localStorage 持久化）+ **贴地形的着色云壳**（见第五节）

**渲染已跑通**：零 JS 错误、面板 13 滑块、参数写进 URL、云有絮状结构与流动、六道门全绿。

## 三、四个已修的关键 bug（别再踩）

| bug | 症状 | 根因 |
|---|---|---|
| GLSL `smoothstep(0.5, 0.06, r)` | 云完全不可见 | 边缘参数降序，GLSL 要求 `edge0 < edge1`，行为未定义。改成 `1.0 - smoothstep(0.0, 0.5, r)` |
| 云值再除 255 | 云不可见 | `dec()` **已归一化到 0..1**（内部 `a[i]/255`），不能再除 |
| `D.cloud` | `D is not defined` | 数据对象叫 **`DATA`**，不是 `D` |
| `STARS.traverse` | `not a function` | `STARS` 是 `{regs, sizeStars}`，不是 Object3D；遍历 `STARS.regs` |

## 四、云是什么（数据层的结论，别重新推导）

云场的定义是 **link reach**：每格记忆到它 top-5 真近邻的**平均大圆弧距**。

| 候选定义 | vs 记忆数 | vs 高度场 | 结论 |
|---|---|---|---|
| 关联**数量** | **+0.998** | +0.057 | ❌ 就是密度，丢弃 |
| 关联**距离** | 真实 −0.395 / demo −0.211 | 真实 **−0.440** / demo −0.235 | ✅ 保留 |

**语义**：云厚 = 这片记忆孤立（真近邻都在球的别处）；云薄 = 抱团。
真实数据上云与陆**反相关 −0.44**，是互补而非正交。

## 五、云（已定稿，2026-11-06 重做）

**结论先说**：云不再是浮空的点精灵场，改成**贴着地形的着色云壳**。旧的"一堆清晰白点"
方案已经删掉，别再按它调参。

### 为什么必须换掉点云（两个结构性理由，调参救不了）

| 问题 | 现象 | 根因 |
|---|---|---|
| 两个剪影 | 大云球套小地球，像棉花糖包装 | 云壳固定半径 1.30 + 地形球 1.0 = 屏幕上两个轮廓 |
| 做不出云纹理 | 永远是均匀灰雾或清晰白点 | 1024 个 sprite 无论怎么分配尺寸/alpha/数量，叠加不出"边缘"和"卷曲" |

**另一个硬约束**：地形半径最大到 1.14（alpha=0.28 时），云层半径低于它就会被地形穿模吃掉，
只剩外圈一条环（实测 cloudR=1.10 时云几乎消失）。所以旧的"浮空云壳"必须 ≥1.25 才可见。

### 现在的实现

- 云壳**复用地形顶点**（同一套 `dirs`），半径 = 该顶点 `r + (P.cloudR - 1.0)`
- 顶点在 `rebuild()` 里与地形同源写入 → **只有一个剪影**，云随地形起伏
- 外观全在片元着色器：32×32 云场决定**哪里**有云（与高度场同一套 lat-long 参数化），
  域扭曲 fbm 决定**怎么撕裂**，两者之间一个 `smoothstep` 给出云团的边
- 云的流动 = 片元里沿经度滑移场查找（`uTime * uFlow`），**不再旋转几何**

### 两个"静默失败"陷阱（都不抛错，症状都长得像"云没渲染"）

| 坑 | 后果 |
|---|---|
| `atan2(y,x)` | GLSL ES 1.00 没有这个函数，双参数版是 **`atan(y,x)`**。整个片元着色器编译失败 → 材质静默不绘制 |
| 共享 `geo.index` 属性实例 | 把地形几何的 index **Attribute** 直接给第二个 geometry，两个几何抢同一份 VAO 绑定 → 云壳用错顶点光栅化，落到地形下面去。共享底层 **array**（`new THREE.BufferAttribute(geo.index.array,1)`）才是安全的 |

排查手法（下次遇到"物体在画但看不见"）：`renderer.info.render.calls` 有它 + 剪影外看不见
→ 大概率是上面两个之一；把材质换成 `MeshBasicMaterial({depthTest:false})` 能立刻区分
"几何/深度问题"和"着色器问题"。

### 调参位置（`template_time.html` 的 `buildCloud()`）

```js
uCov   = 0.46 - 0.24*P.density                      // 云覆盖率阈值，密度↑云多
uScale = 5.5 / max(0.3, P.spriteScale)              // 云团尺度，值小=团大
uFlow  = P.cloudSpin * 0.020                        // 云流速
'float cov = smoothstep(uCov, uCov+0.42, v*(0.30+1.45*n));'   // 场×噪声 → 云量
'float a = cov * uOp * (0.88 - 0.88*limb);'          // limb 淡出到 0，防灰边
```

`cloudR` 语义已变：**不再是云壳半径，是"云层高出地形的高度"**（1.00–1.40 → 0.00–0.40）。
所以 localStorage 的 key 升到 `ms.sphere.look.v2`，旧值不会污染新页面。

## 六、怎么跑

```bash
cd /d/memory-sphere
export SPHERE_OUT=D:/memory-sphere/out
# 构建（用 runtime 的 python；它没有 scipy，所以不能跑 build_cloud.py）
"C:/Users/Administrator/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" -m sphere build

# 云场要用系统 python（有 scipy）
"C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe" sphere/pipeline/build_cloud.py

# 本地看
cd out && python -m http.server 8801
# → http://127.0.0.1:8801/sphere_timeline.html
```

**参数全程走 URL**，例如：
```
?cloudR=1.32&density=0.55&bigWeight=0.6&spriteScale=1&cloudOpacity=0.85&cloudSpin=0.22
```

## 七、未完成清单

1. ~~**云观感调优**~~ ✅ 已定稿（第五节），点云方案已删除
2. **切回 demo 数据**：验证完把 `data/input` 换回 `data/input_demo`，重跑 build + build_cloud
3. **那句会撒谎的文案**：页面左上角「demo 页面：合成的记忆，不含任何私有数据」—— 用真实数据时它是错的，切回 demo 才对。若今后要发布真实数据版本，这行必须改成动态或删掉
4. ~~**门禁**~~ ✅ 已加：`check_render.py` 现在断言云壳（材质/纹理/自有 index/高度语义/`atan(y,x)` 写法）+ 数据层「云与陆 |spearman| < 0.6」（实测 −0.462）
5. **发布**：v1.2.0 的 CHANGELOG（双语）、tag、Release、Pages 更新
6. **云与时间维度的关系**：云场是全期聚合的，不随时间帧变化；地形在变。若希望云也随时间演化，需要 `gen_web_data.py` 导出逐帧云场（现在没有）

## 八、别忘的既有约束

- 自转门禁：`scripts/check_hero_spin.py`，球体位移 `1 + alpha*(h-0.5)` 不能动
- 双语门禁：`scripts/check_bilingual_sync.py`
- 版本门禁：`scripts/check_version_sync.py`
- 区域门禁：`scripts/check_regions.py`
- 搜索门禁：`scripts/check_search.py`
- 渲染门禁：`scripts/check_render.py`

七道门现在全绿，改完要重跑。