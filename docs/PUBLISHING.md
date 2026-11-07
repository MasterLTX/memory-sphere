# 第一次把这个项目推上 GitHub

手把手版。假设你从没开源过，跟着做就行。所有命令在 **Git Bash / PowerShell** 里都能跑。

---

## 0. 一次性准备：告诉 git 你是谁

```bash
git config --global user.name  "你的名字"
git config --global user.email "你的GitHub邮箱"
```

> 这两项会写进每个 commit。用错了以后所有提交都是错的身份，改起来要重写历史。

---

## 1. 在 GitHub 网页上建一个**空**仓库

1. 右上角 `+` → **New repository**
2. Repository name：`memory-sphere`
3. 选 **Public**
4. ⚠️ **三个勾选框全部不要勾**（Add README / .gitignore / license）
   —— 你本地已经有这些文件了，勾了会产生两个互不相干的历史，push 时会冲突
5. 点 **Create repository**

建好后页面会显示一堆命令，先别管，往下走。

---

## 2. 把本地仓库接到 GitHub

```bash
cd /d/memory-sphere

# 用你自己的用户名替换 <you>
git remote add origin https://github.com/<you>/memory-sphere.git

# 确认分支名（本仓库已经是 main）
git branch -M main

# 推上去
git push -u origin main
```

### 第一次 push 会要密码 —— 这里有个坑

GitHub 从 2021 年起**不接受账号密码**，要 **Personal Access Token**：

1. GitHub → 头像 → **Settings** → 左下 **Developer settings**
2. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
3. Note 随便填，Expiration 选 90 天，勾选 **`repo`** 这一个就够
4. 生成后**立刻复制**（页面关掉就再也看不到）
5. 回到终端：用户名填你的 GitHub 用户名，**密码位置粘贴那个 token**

> Token 等同于密码，别贴进任何文件、别提交进仓库。
> 想省事可以改用 SSH：`ssh-keygen -t ed25519` 然后把 `~/.ssh/id_ed25519.pub` 填到 GitHub → Settings → SSH keys。

---

## 3. 确认推上去了

打开 `https://github.com/<you>/memory-sphere`，应该能看到 README 和那个旋转 GIF。

如果 README 顶部没显示 GIF，多半是 `examples/rotating.gif` 没被推上去——检查：

```bash
git ls-files examples/
```

---

## 4. 开 GitHub Pages（让别人点开就能转球）

1. 仓库 → **Settings** → 左侧 **Pages**
2. **Source** 选 `Deploy from a branch`
3. **Branch** 选 `main`，目录选 **`/docs`**
4. **Save**，等 1–2 分钟

访问 `https://<you>.github.io/memory-sphere/` 就能直接玩。

> 仓库里 `docs/index.html` 就是演示页。重新生成后覆盖它、再 push 即可更新。

---

## 5. 打第一个版本标签（Release）

发布正式版后，别人可以按版本下载，也方便写进 README 徽章。

```bash
git tag -a v1.0.0 -m "v1.0.0 — first public release"
git push origin v1.0.0
```

然后网页上：仓库 → **Releases** → **Draft a new release** → 选 `v1.0.0` → 标题和说明随便写几句 → **Publish release**。

---

## 6. 发布前自检：四道人工 + 三道自动

```bash
# ① 有没有敏感东西混进来（应该没有任何输出）
git grep -nE "密码|password|token|secret|你们公司名|你的用户名" -- . ':!docs/PUBLISHING.md'

# ② 有没有大文件（>5MB 会被 GitHub 警告，>100MB 直接拒绝）
git ls-files | xargs -I{} du -h {} 2>/dev/null | sort -rh | head -5

# ③ docs/ 里只能有发布产物（这一条是踩坑后加的，见下面的说明）
git ls-files docs/

# ④ 干净环境能不能跑（最重要）
python -m venv /tmp/clean && /tmp/clean/bin/pip install -r requirements.txt
/tmp/clean/bin/python -m sphere demo

# ⑤ 三道自动门禁：任何一道不过就别发
python scripts/check_version_sync.py --no-tag   # 打 tag 前跑；打完 tag 去掉 --no-tag 复核
python scripts/check_bilingual_sync.py          # 中英两版有没有漂移
python scripts/check_hero_spin.py               # 首屏 GIF 到底在怎么转
```

> **③ 为什么单独列一条**：`docs/` 是 Pages 的发布根目录，里面的**每一个文件都会被当成网页公开**，
> 不只是 `index.html`。把交接笔记、内部记录、草稿放进 `docs/`，它们就会出现在
> `https://<you>.github.io/<repo>/xxx.md` 上。内部文档一律放 `_private/`（已在 `.gitignore` 里），
> 或者根本不要 `git add`。
>
> 相应地，`docs/` 里应当只有：`index.html`（页面）、页面运行时按需加载的 `web_data.extra.json`、
> 以及这份 `PUBLISHING.md`。多出任何东西，先问一句"它该被公开吗"再提交。

---

## 7. 常见的四个坑

| 坑 | 表现 | 解法 |
|---|---|---|
| 建仓库时勾了 README | `push` 报 `rejected (fetch first)` | `git pull --rebase origin main` 后再 push |
| 用了账号密码 | `Authentication failed` | 用 PAT（见 §2） |
| 提交了真实数据 | 仓库里出现不该出现的记忆 | **立刻**改 `.gitignore` + `git rm --cached`，然后必须**重写历史**（`git filter-repo`）——这步很难，所以脱敏要在第一次 commit 前做完 |
| 大文件 | GitHub 拒绝 push | 别提交 `out/`、`vendor/`、`.gif` 以外的产物，`.gitignore` 已挡 |

---

## 8. 推上去之后

- **描述和话题**：仓库首页右上 ⚙️ → Description 填一句话，Topics 填
  `vector-visualization` `dimensionality-reduction` `memory` `threejs` `pgvector`
- **README 里的 `<you>`**：把占位符换成你的用户名，否则 clone 命令是坏的
- 发到社区时，链接用 `https://<you>.github.io/memory-sphere/`（可玩的），
  而不是仓库首页——**能直接转起来的东西转发率高得多**

---

## 附：本仓库当前状态速查

```bash
git log --oneline          # 提交历史
git ls-files | wc -l       # 跟踪了多少文件
git remote -v              # 远程地址（本仓库已经配置好了）
```

本仓库已经发布过 v1.0.0 和 v1.0.1，所以 `origin` 是存在的；上面这几条命令
是给你检查自己的 fork、或者重新初始化出来的副本用的。