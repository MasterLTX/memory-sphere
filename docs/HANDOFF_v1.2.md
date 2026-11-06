# v1.2 交接（云层 + 参数面板）

写于 2026-11-06 10:56，因为当前会话体积已达 9.46 M 字符，超过昨天 413 挂掉时的
5.72 M，随时可能断。读这一份就能接上，不必翻对话。

---

## 一、当前状态

| 项 | 状态 |
|---|---|
| 仓库 | `D:\memory-sphere`，GitHub `MasterLTX/memory-sphere` |
| 已发布版本 | **v1.1.0**（tag 已推，Release 已发，Pages 已上线） |
| 工作分支 | `main`，最新 commit `1a39a89`（云层 + 面板，**未推送**） |
| 数据源 | **当前是真实数据**（10,790 条 × 1024 维 + 120k links），demo 备份在 `data/input_demo/` |

## 二、v1.2 做到哪了

**已完成并提交**：
- `sphere/pipeline/build_cloud.py` —— 云场（reach 定义，双尺度平滑，分块 kNN）
- `sphere/pipeline/gen_web_data.py` —— 导出 `DATA.cloud.{big,small}`
- `template_time.html` —— 浮空云壳（R=1.30，独立转速）+ 13 个滑块的参数面板（URL + localStorage 持久化）

**渲染已跑通**：零 JS 错误、面板 13 滑块、参数写进 URL。

**没做完**：**云的观感**。当前云是"一堆清晰白点飘在球外"，不像云。见下面调参位置。

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

## 五、云的调参位置（当前最该改的地方）

`template_time.html` 的 `buildCloud()` 里，四个参数决定观感：

```js
const n = Math.max(1, Math.round(dens*9.0*v));      // 每格点数 → 越大越密
siz.push((0.13 + 0.30*v) * P.spriteScale);          // 单点尺寸
alp.push(Math.min(1, v*0.42*P.cloudOpacity));       // 单点不透明度
'gl_PointSize = aSize * 760.0 / max(0.001, -mv.z);' // 屏幕像素尺寸
float a = pow(1.0 - smoothstep(0.0, 0.5, r), 1.6) * vA;  // 软边
```

**当前观感问题**：点是硬边小圆，像雪粒/白点，不成雾。
**方向**：更多点数 + 更大尺寸 + 更低 alpha（叠加才成雾），alpha 再降一半、尺寸再涨 1.5 倍试试；
或者改用 canvas 径向渐变纹理的 `PointsMaterial`（`STARS` 里已有现成的渐变纹理生成代码可抄）。

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

1. **云观感调优**（上面第五节）—— 当前最优先
2. **切回 demo 数据**：验证完把 `data/input` 换回 `data/input_demo`，重跑 build + build_cloud
3. **那句会撒谎的文案**：页面左上角「demo 页面：合成的记忆，不含任何私有数据」—— 用真实数据时它是错的，切回 demo 才对。若今后要发布真实数据版本，这行必须改成动态或删掉
4. **门禁**：`check_render.py` 需要加云层断言 + "云与陆 |spearman| < 0.6" 的断言
5. **发布**：v1.2.0 的 CHANGELOG（双语）、tag、Release、Pages 更新

## 八、别忘的既有约束

- 自转门禁：`scripts/check_hero_spin.py`，球体位移 `1 + alpha*(h-0.5)` 不能动
- 双语门禁：`scripts/check_bilingual_sync.py`
- 版本门禁：`scripts/check_version_sync.py`
- 区域门禁：`scripts/check_regions.py`
- 搜索门禁：`scripts/check_search.py`
- 渲染门禁：`scripts/check_render.py`

七道门现在全绿，改完要重跑。