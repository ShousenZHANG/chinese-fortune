# 发布与来源归档

运行包始终包含五书全部 416 章，不划分精简版和完整版。原始网页、目录捕获、来源元数据与 SKchar 字形映射保留在源码，以及同次构建的 `*-sources.zip`。正文仍保留原始来源指针；运行清单的 `source_paths_scope=source_archive/knowledge` 明确它们位于来源归档内。

`knowledge/manifest.json` 使用 schema 2.0，必须声明 `distribution_kind`。`source` 校验全部正文、目录、raw 文件和 supporting_sources 的字节摘要；任一缺失都失败。`runtime` 校验全部运行文件、正文、章节清单及来源归档索引，但不声称重新校验未安装的 raw 文件。两种结果的 `validation_scope` 和 `raw_sources_verified` 分别报告。不能根据 sources 目录是否存在决定跳过校验。

构建先做全量源码校验，再验证实际暂存的来源字节，生成来源 ZIP 并把其 SHA256 写入运行清单，最后验证实际暂存的运行文件。运行清单记录所有其他运行文件摘要，不记录自己的摘要。外部 `SHA256SUMS` 覆盖完整运行 ZIP 和来源 ZIP，包括各自清单。许可、版本、来源说明与转录边界留在运行包；这些校验不等于原刻影像校勘或现实预测验证。

## 开发构建

```powershell
python scripts/build_skill.py --dist-dir dist
```

`RELEASE.json` 记录版本和 `build.mode=development`、当前提交、`dirty`。运行输入存在修改或未跟踪文件时标 dirty；无关未跟踪的用户笔记不会阻止构建。没有 Git 元数据的开发副本也可以构建，但 commit 为 null、dirty 为 true。开发包不能当成受测提交的正式包。

## 固定提交和 CI

```powershell
$releaseCommit = git rev-parse HEAD
python scripts/build_skill.py --commit $releaseCommit --dist-dir dist
```

`--commit` 必须是完整提交 SHA。构建器用 Git archive 创建临时快照，运行该提交自带的构建器和校验器，不读取未提交的运行文件，也不删除或移动工作树中的笔记。快照内包标为 `commit_snapshot`，记录完整 SHA。老版本若不支持该接口会失败，不能用现在的构建逻辑冒充旧版本的受测构建。快照子进程还会按 Git 对象格式重算全部文件的 blob/tree 摘要，与提交对象中绑定的 tree 比较，并校验提交对象 SHA；仅传入内部参数或伪造 commit 标签不会变成正式包。

CI 在 Python 3.11/3.12 跑完整 pytest、lint 和类型检查。覆盖率总门槛保持 80%，包含 scripts 与 evals，构建器也计入；运行时代码和维护工具的分组报告使用同一份数据。Windows 另跑包安装、UTF-8 和时间边界检查。`slow` 只允许用于本地明确选择的快速集，CI 不排除。

Python 3.12 的 CI 使用 `${{ github.sha }}` 构建，然后通过 `package_smoke.py --archive ... --expected-commit ...` 安装和执行这一份 ZIP。成功后上传 `chinese-fortune-skill` artifact，包含两个 ZIP、SHA256SUMS、CI-PROVENANCE.json。构建后不再次生成发布 ZIP。只有整个 workflow conclusion 为 success 才能发布，不能仅凭 artifact 已上传或其中自述的 run_id 判定成功。

## 下载与发布核对

选取当前 main 上已全部成功的 CI run，记录 run ID、完整 commit、artifact 名称及 GitHub artifact digest（可用时）。下面命令只演示下载和核对，不创建发布：

```powershell
$releaseRunId = '<successful-run-id>'
$releaseCommit = '<full-40-character-commit>'
$releaseRun = gh run view $releaseRunId --json headSha,headBranch,conclusion | ConvertFrom-Json
if ($releaseRun.headSha -ne $releaseCommit -or $releaseRun.headBranch -ne 'main' -or $releaseRun.conclusion -ne 'success') { throw 'CI identity or conclusion mismatch' }
$downloadDir = "release-download/$releaseCommit"
if (Test-Path -LiteralPath $downloadDir) { throw 'Choose a fresh download directory' }
gh run download $releaseRunId -n chinese-fortune-skill -D $downloadDir
$provenance = Get-Content -LiteralPath "$downloadDir/CI-PROVENANCE.json" -Raw | ConvertFrom-Json
if ($provenance.commit -ne $releaseCommit -or $provenance.ci_run_id -ne $releaseRunId) { throw 'Artifact provenance mismatch' }
if ($provenance.checksums -cne (Get-Content -LiteralPath "$downloadDir/SHA256SUMS" -Raw)) { throw 'CI checksum record mismatch' }
$runtimeZip = @(Get-ChildItem -LiteralPath $downloadDir -Filter '*.zip' | Where-Object { $_.Name -notlike '*-sources.zip' })
if ($runtimeZip.Count -ne 1) { throw 'Expected exactly one runtime ZIP' }
python -X utf8 evals/package_smoke.py --archive $runtimeZip[0].FullName --expected-commit $releaseCommit --verify-only
if ($LASTEXITCODE -ne 0) { throw 'Artifact verification failed' }
```

发布时复用该下载目录的原始附件，标签只能指向该受测提交，不能覆盖已有标签。主仓库只维护 main，不为发布新建 PR 或长期分支。若 main 有新提交，等待新提交的完整 CI，或明确发布已核验的旧提交；不要把旧 CI 结果套到新代码。

发布后把公开附件下载到另一个新目录，再执行相同的 `--verify-only --expected-commit` 检查，并将公开 SHA256SUMS 与受测下载目录逐字节比较。记录远端 release URL、tag/commit、CI run、运行包和来源包 SHA256；本地重新构建成功不能替代这一步公开附件核对。

## 检查入口与保护力

原 `run_checks.py` 独有的 CLI 黄金断言迁入 pytest，失败输入契约、Markdown 可达性、包完整性和新环境安装仍保留。重复启动 pytest 的 harness、固定措辞/欠账数量/脚本行数断言已移除。源码原地变异器及会写入真实 utils.py 的守卫已删除；变异只能在内存或临时副本进行。

六爻测试按《卜筮正宗》卷一的八宫序列与世应位置独立核对 64 卦，并在内存中把世应一起错移一位、同步修改标记，证明新断言能够检出这种旧检查漏过的错误。所核网页为[识典古籍卷一转录](https://www.shidianguji.com/book/AMNL0060/chapter/1ma05akk4w74j)，不是原刻影像逐字校勘。测试保护力、模型回答语义评审和实际预测验证分别记录。
