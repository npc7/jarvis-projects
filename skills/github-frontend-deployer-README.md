# GitHub Frontend Deployer Skill

An OpenClaw skill for automatically deploying frontend projects to GitHub Pages with Telegram notifications.

## What It Does

This skill helps OpenClaw agents:
1. Detect frontend project types (HTML, Node.js, Jekyll, Hugo, Next.js)
2. Create appropriate GitHub Actions workflows
3. Configure deployment to GitHub Pages
4. Send Telegram notifications with live URLs
5. Generate deployment documentation

## Skill Package

The skill is packaged as `github-frontend-deployer.skill` - a distributable OpenClaw skill file.

## Usage

### For OpenClaw Agents
When a user requests frontend deployment:

1. **Load the skill** - The skill triggers when users ask about deploying frontend projects
2. **Detect project** - Use `scripts/detect_project.py` to identify project type
3. **Create workflow** - Use `scripts/create_workflow.py` to generate GitHub Actions workflow
4. **Configure notifications** - Set up Telegram bot if desired
5. **Guide user** - Provide deployment instructions

### For Developers
1. **Install the skill** in your OpenClaw workspace
2. **Ask OpenClaw** to deploy your frontend project
3. **Follow the instructions** provided by the agent

## Example Usage

```
User: "Deploy my snake game to GitHub Pages"
OpenClaw (with skill): 
1. Detects snake game as HTML project
2. Creates .github/workflows/deploy.yml
3. Provides deployment instructions
4. Sends URL when deployment completes
```

## Projects Tested

### 1. Snake Game (HTML)
- Simple HTML/CSS/JavaScript game
- No build process needed
- Deploys directly from source

### 2. MAS Compliance Report (Node.js)
- Interactive web application
- Requires `npm run build`
- Output to `dist` directory

## Features

### Project Detection
- HTML projects (index.html)
- Node.js projects (package.json)
- Static site generators (Jekyll, Hugo)
- Next.js with static export

### Workflow Templates
- Pre-configured GitHub Actions workflows
- Latest action versions
- Best practices included
- Customizable for different project types

### Notification System
- Telegram bot integration
- Deployment status updates
- Live URL sharing
- Error reporting

### Configuration Management
- Project-specific configuration
- Environment variable handling
- Secret management guidance
- Deployment options

## Files Included

### Skill Structure
```
github-frontend-deployer/
├── SKILL.md              # Skill instructions
├── scripts/
│   ├── detect_project.py     # Project detection
│   ├── create_workflow.py    # Workflow creation
│   └── send_notification.py  # Telegram notifications
├── references/
│   ├── github-actions-reference.md
│   └── telegram-bot-setup.md
└── assets/
    └── workflow-templates/   # Template files
```

### Generated Files
When the skill runs on a project:
- `.github/workflows/deploy.yml` - GitHub Actions workflow
- `deploy-config.json` - Deployment configuration
- `DEPLOYMENT.md` - Instructions for the user

## Setup Requirements

### For Deployment
1. GitHub repository with frontend code
2. GitHub Pages enabled (or willingness to enable it)
3. Push access to the repository

### For Notifications (Optional)
1. Telegram bot token (from @BotFather)
2. Telegram chat ID
3. GitHub secrets configured

## Quick Start

1. **Have OpenClaw load the skill**
2. **Ask**: "Deploy my frontend project to GitHub Pages"
3. **Follow** the agent's instructions
4. **Commit and push** the generated workflow
5. **Enable GitHub Pages** in repository settings
6. **Receive URL** when deployment completes

## Benefits

- **Time-saving**: Automates repetitive setup
- **Consistent**: Uses best practices for all projects
- **Educational**: Guides users through the process
- **Extensible**: Easy to add new project types
- **Shareable**: Other OpenClaw users can use it

## Limitations

- Currently supports GitHub Pages only (Netlify/Vercel planned)
- Requires manual GitHub Pages enabling
- Project must be in a GitHub repository
- Complex monorepos may need custom configuration

## Future Enhancements

1. Support for multiple deployment targets (Netlify, Vercel, Cloudflare)
2. Automatic GitHub Pages enabling via API
3. Preview deployments for pull requests
4. Custom domain configuration
5. Performance optimization checks

## Contributing

This skill is open for improvements. To contribute:
1. Fork the repository
2. Make changes to the skill files
3. Test with sample projects
4. Submit a pull request

## License

MIT License - See LICENSE file in skill package.

## Author

Created by Jarvis (Max's OpenClaw assistant) for the TrustIn team.