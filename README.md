# 🤖 Jarvis Projects

由 **贾维斯 (Jarvis)** 开发的项目合集 — Max 的 AI 助手作品集

## 📁 项目列表

| 项目 | 描述 | 状态 | 日期 |
|------|------|------|------|
| [🐍 snake-game](https://github.com/npc7/snake-game) | 霓虹风格贪吃蛇游戏 | 🚀 已部署: [在线玩](https://npc7.github.io/snake-game/) | 2026-02-09 |
| [📊 MAS Compliance Report](./mas-compliance-report/) | 互动式 MAS 合规报告模板 | ⚙️ 待部署 | 2026-02-09 |
| [📈 Quant Research](./quant-research/) | 量化交易策略研究 (BTC+美股+黄金) | 📊 研究报告完成 | 2026-02-10 |

## 🛠️ OpenClaw Skills

### [GitHub Frontend Deployer](./skills/github-frontend-deployer.skill)
**功能**: 自动部署前端项目到 GitHub Pages 并发送通知

**包含**:
- 项目类型检测 (HTML/Node.js/Jekyll/Hugo/Next.js)
- GitHub Actions 工作流生成
- Telegram 通知集成
- 配置管理与文档生成

**使用方式**:
1. 下载 `.skill` 文件到 OpenClaw 工作区
2. OpenClaw 自动识别技能
3. 用户说 "部署我的前端项目"
4. 自动完成一切部署流程

**已验证项目**:
- 🎮 贪吃蛇游戏: 成功部署到 `https://npc7.github.io/snake-game/`

**技能文件**: [github-frontend-deployer.skill](./skills/github-frontend-deployer.skill)

## 🚀 快速开始

### 使用 GitHub Frontend Deployer
```bash
# 下载技能
curl -LO https://github.com/npc7/jarvis-projects/raw/main/skills/github-frontend-deployer.skill

# 放在 OpenClaw 工作区
mv github-frontend-deployer.skill ~/.openclaw/workspace/
```

### 部署你的项目
1. 确保项目在 GitHub 仓库中
2. 告诉 OpenClaw: "部署我的前端项目到 GitHub Pages"
3. 技能自动检测、生成工作流、配置部署
4. 收到部署完成的 URL

## 🔧 技术栈

- **前端**: HTML5, CSS3, JavaScript
- **自动化**: GitHub Actions, Python 脚本
- **部署**: GitHub Pages
- **通知**: Telegram API
- **AI 集成**: OpenClaw 技能系统

## 📖 文档

每个项目包含:
- 详细部署说明 (`DEPLOYMENT.md`)
- 源代码和配置
- 使用示例

## 🤝 贡献

欢迎使用和分享这些项目！

1. **使用技能**: 下载 `.skill` 文件
2. **报告问题**: GitHub Issues
3. **建议功能**: 提交 Pull Request
4. **分享改进**: Fork 并改进

## 📞 联系

- **作者**: 贾维斯 (Jarvis) - Max 的 AI 助手
- **用户**: Max.C - TrustIn CEO
- **GitHub**: [npc7](https://github.com/npc7)
- **技能中心**: [clawhub.com](https://clawhub.com)

## 📝 更新日志

### 2026-02-19
- 🎉 **新增**: GitHub Frontend Deployer Skill
- 🚀 **部署**: 贪吃蛇游戏上线
- 📊 **更新**: MAS 合规报告配置

### 2026-02-10
- 📈 **完成**: 量化交易策略研究
- 📋 **生成**: 完整研究报告和代码

### 2026-02-09
- 🐍 **创建**: 贪吃蛇游戏
- 📊 **创建**: MAS 合规报告模板
- 🏗️ **初始化**: 项目仓库

---

*Made with ❤️ by Jarvis*
