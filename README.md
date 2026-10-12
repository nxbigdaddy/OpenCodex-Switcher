# OpenCodex Switcher

一个面向 Windows 的 Codex 模型配置管理器，用于安全地管理和切换自定义模型服务商。

当前版本包含：

- 读取用户级 `~/.codex/config.toml`
- 管理服务商与模型模板
- 测试 `/responses` 兼容性
- 自绘无系统标题栏窗口
- 内置关键字段与原始 TOML 配置编辑器
- 设置、自动检测并保存当前 Codex 桌面程序路径
- 查看 Codex 运行状态，以及启动、正常关闭和确认后强制关闭
- 内置 Windows 用户级/系统级环境变量读取、保存和删除
- 预设 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 等常用变量
- 应用配置前自动备份
- TOML 差异预览、原子写入与回滚
- 环境变量和配置冲突诊断

## 运行

```powershell
python .\app.py
```

开发阶段推荐直接双击 `run.bat`，或执行：

```powershell
.\run.bat
```

安装依赖：

```powershell
python -m pip install -r .\requirements.txt
```

运行测试：

```powershell
python -m pytest
```

无副作用启动检查：

```powershell
python .\app.py --smoke-test
```

## 安全策略

- API Key 不会写入 `config.toml` 或服务商 JSON。
- 只有用户明确点击“应用配置”才会修改真实 Codex 配置。
- 修改前自动备份，失败时保留原配置。
- 连接测试日志不会记录完整 API Key。
- Codex 程序控制只接受 `.exe`，并按完整可执行文件路径精确匹配进程，不会仅按进程名批量关闭。
- Codex 路径保存在 `%LOCALAPPDATA%\OpenCodexSwitcher\app-settings.json`。
- 敏感环境变量默认隐藏，保存后不会在日志或提示中显示变量值。
- 系统范围环境变量写入需要管理员权限；环境变化只对新进程生效，已经运行的 Codex 需要重启。

---

## 许可证

本项目采用 [MIT 许可证](LICENSE)。

## 第三方与上游声明

本项目包含或依赖第三方组件，其版权与许可证归各自作者所有，
详见仓库内的依赖清单与相关声明文件。若本项目基于其他开源项目二次开发，
已在正文中注明上游项目与所基于的版本，本项目为**非官方**衍生作品。

## 现状与限制

- 本项目为个人开发项目，按“现状”提供，不附带任何明示或暗示的担保。
- README 与代码注释中记录的验证结论仅针对当时的具体环境与版本，不代表在其他环境下同样成立。
- 涉及本地凭据的部分统一使用系统凭据库或环境变量，仓库内不含真实密钥；
  示例配置仅使用占位符。
