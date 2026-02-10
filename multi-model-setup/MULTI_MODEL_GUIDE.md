# 🔀 OpenClaw 多模型路由配置方案

> 解决单一模型限额问题，实现智能 failover

---

## 📊 当前状态

```json
{
  "model": {
    "primary": "anthropic/claude-opus-4-5"  // 只有一个模型
  }
}
```

**问题**: Claude 有 API 限额，用完就停摆

---

## 🎯 目标架构

```
请求 → 主模型 (Claude Opus) 
         ↓ 限额/失败
       备用1 (Claude Sonnet)
         ↓ 限额/失败
       备用2 (GPT-4o)
         ↓ 限额/失败  
       备用3 (Gemini Pro)
         ↓ 限额/失败
       备用4 (DeepSeek)
```

---

## 🔧 配置方案

### 方案 A: 简单 Fallback (推荐新手)

修改 `~/.openclaw/openclaw.json`:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-5",
        "fallbacks": [
          "anthropic/claude-sonnet-4",
          "openai/gpt-4o",
          "google/gemini-2.0-flash"
        ]
      }
    }
  }
}
```

**需要配置的 API Keys**:
- `ANTHROPIC_API_KEY` - Anthropic
- `OPENAI_API_KEY` - OpenAI
- `GOOGLE_API_KEY` - Google

---

### 方案 B: 多账号 + Fallback (推荐)

使用多个 API 账号，同一模型不同额度：

```json
{
  "auth": {
    "profiles": {
      "anthropic:primary": {
        "provider": "anthropic",
        "mode": "api_key"
      },
      "anthropic:backup": {
        "provider": "anthropic", 
        "mode": "api_key"
      },
      "openai:default": {
        "provider": "openai",
        "mode": "api_key"
      },
      "google:default": {
        "provider": "google",
        "mode": "api_key"
      }
    },
    "order": {
      "anthropic": ["anthropic:primary", "anthropic:backup"],
      "openai": ["openai:default"],
      "google": ["google:default"]
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-5",
        "fallbacks": [
          "anthropic/claude-sonnet-4",
          "openai/gpt-4o",
          "google/gemini-2.0-flash"
        ]
      }
    }
  }
}
```

**环境变量设置**:
```bash
# ~/.zshrc 或 ~/.bashrc

# Anthropic 主账号
export ANTHROPIC_API_KEY="sk-ant-xxx-primary"

# Anthropic 备用账号 (需要另一个账号)
export ANTHROPIC_API_KEY_BACKUP="sk-ant-xxx-backup"

# OpenAI
export OPENAI_API_KEY="sk-xxx"

# Google
export GOOGLE_API_KEY="AIza-xxx"
```

---

### 方案 C: OpenRouter 一站式 (最省事)

OpenRouter 汇聚 100+ 模型，一个 API Key 访问所有：

```json
{
  "models": {
    "providers": {
      "openrouter": {
        "baseUrl": "https://openrouter.ai/api/v1",
        "apiKey": "${OPENROUTER_API_KEY}",
        "api": "openai-completions",
        "models": [
          {
            "id": "anthropic/claude-opus-4",
            "name": "Claude Opus 4 (OpenRouter)"
          },
          {
            "id": "openai/gpt-4o",
            "name": "GPT-4o (OpenRouter)"
          },
          {
            "id": "google/gemini-2.0-flash-thinking",
            "name": "Gemini Flash (OpenRouter)"
          },
          {
            "id": "deepseek/deepseek-r1",
            "name": "DeepSeek R1 (OpenRouter)"
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/anthropic/claude-opus-4",
        "fallbacks": [
          "openrouter/openai/gpt-4o",
          "openrouter/deepseek/deepseek-r1"
        ]
      }
    }
  }
}
```

**优点**:
- ✅ 一个账号访问所有模型
- ✅ 统一计费
- ✅ 自动路由

**获取 Key**: https://openrouter.ai/keys

---

### 方案 D: 子任务用不同模型 (省钱)

主对话用高端模型，后台任务用便宜模型：

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-5"
      },
      "subagents": {
        "model": "anthropic/claude-sonnet-4",
        "maxConcurrent": 8
      }
    }
  }
}
```

**效果**:
- 你跟我聊天 → Claude Opus (最强)
- 后台研究任务 → Claude Sonnet (便宜 10x)

---

## 📋 完整推荐配置

```json
{
  "auth": {
    "profiles": {
      "anthropic:default": {
        "provider": "anthropic",
        "mode": "api_key"
      },
      "openai:default": {
        "provider": "openai",
        "mode": "api_key"
      },
      "google:default": {
        "provider": "google",
        "mode": "api_key"
      }
    },
    "cooldowns": {
      "billingBackoffHours": 2,
      "billingMaxHours": 12
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-5",
        "fallbacks": [
          "anthropic/claude-sonnet-4",
          "openai/gpt-4o", 
          "google/gemini-2.0-flash"
        ]
      },
      "imageModel": {
        "primary": "openai/gpt-4o"
      },
      "subagents": {
        "model": {
          "primary": "anthropic/claude-sonnet-4",
          "fallbacks": ["openai/gpt-4o-mini"]
        },
        "maxConcurrent": 8
      }
    }
  }
}
```

---

## 🛠️ 你需要做的

### Step 1: 获取 API Keys

| 提供商 | 获取地址 | 价格 |
|--------|----------|------|
| Anthropic | https://console.anthropic.com | Opus $15/M, Sonnet $3/M |
| OpenAI | https://platform.openai.com | GPT-4o $5/M |
| Google | https://aistudio.google.com | Gemini Flash $0.075/M |
| OpenRouter | https://openrouter.ai | 汇总价格 |
| DeepSeek | https://platform.deepseek.com | R1 $2.19/M (超便宜) |

### Step 2: 设置环境变量

```bash
# 编辑 ~/.zshrc
nano ~/.zshrc

# 添加以下内容
export ANTHROPIC_API_KEY="sk-ant-xxx"
export OPENAI_API_KEY="sk-xxx"
export GOOGLE_API_KEY="AIza-xxx"

# 保存后生效
source ~/.zshrc
```

### Step 3: 更新 OpenClaw 配置

```bash
# 编辑配置
nano ~/.openclaw/openclaw.json

# 或者让我帮你自动配置（提供 API Keys 后）
```

### Step 4: 重启 OpenClaw

```bash
openclaw gateway restart
```

---

## 💡 省钱技巧

1. **主对话用 Opus，子任务用 Sonnet** - 省 80%
2. **简单问题用 Gemini Flash** - 便宜 200x
3. **代码任务用 DeepSeek** - 便宜又强
4. **开 OpenRouter 自动路由** - 最便宜的模型优先

---

## ❓ 需要我帮你配置吗？

提供以下信息，我帮你自动设置：

1. 你有哪些 API Keys？
2. 预算大概多少？
3. 主要用途是什么？

然后我直接帮你改配置并重启！
