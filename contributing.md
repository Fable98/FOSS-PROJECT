# Contributing to SubTerra 💧

First off — thank you for taking the time to contribute! SubTerra is an open-source project built for India's groundwater future, and every contribution matters.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

---

## 📜 Code of Conduct

This project follows a [Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you are expected to uphold it. Please report unacceptable behavior to the maintainers.

---

## 🙋 How Can I Contribute?

There are many ways to contribute — you don't have to write code!

| Type | Examples |
|------|---------|
| 🐛 **Bug Reports** | Found something broken? Open an issue |
| ✨ **Feature Requests** | Have an idea? We'd love to hear it |
| 📖 **Documentation** | Improve README, docs, or code comments |
| 🔧 **Code** | Fix bugs, add features, write tests |
| 🎨 **Design** | UI/UX improvements for the dashboard |
| 🧪 **Testing** | Write unit or integration tests |
| 🌍 **Data** | Help identify new data sources |

---

## 🚀 Getting Started

### 1. Fork the Repository

Click the **Fork** button on the top right of the GitHub page.

### 2. Clone Your Fork

```bash
git clone https://github.com/YOUR_USERNAME/subterra.git
cd subterra
```

### 3. Set Up the Project

Follow the setup guide in [docs/setup-guide.md](./docs/setup-guide.md).

Quick version:

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 4. Add the Upstream Remote

```bash
git remote add upstream https://github.com/originalrepo/subterra.git
```

This lets you pull in future changes from the main repo.

---

## 🔄 Development Workflow

### Step 1 — Sync with Main Repo

Always start from an up-to-date main branch:

```bash
git checkout main
git pull upstream main
```

### Step 2 — Create a Branch

Name your branch clearly based on what you're doing:

```bash
# For a bug fix
git checkout -b fix/station-map-loading

# For a new feature
git checkout -b feature/recharge-algorithm

# For documentation
git checkout -b docs/api-reference-update
```

**Branch naming convention:**

| Prefix | Use for |
|--------|---------|
| `feature/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `test/` | Adding or fixing tests |
| `refactor/` | Code cleanup, no new features |
| `chore/` | Dependency updates, configs |

### Step 3 — Make Your Changes

Write your code, tests, and documentation.

### Step 4 — Test Your Changes

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test
```

Make sure all tests pass before submitting.

### Step 5 — Commit Your Changes

```bash
git add .
git commit -m "feat: add recharge estimation algorithm for Task 2"
```

See [Commit Message Guidelines](#commit-message-guidelines) below.

### Step 6 — Push & Open a Pull Request

```bash
git push origin feature/your-branch-name
```

Then go to GitHub and open a **Pull Request** against the `main` branch.

---

## ✍️ Coding Standards

### Python (Backend)

- Follow **PEP 8** style guidelines
- Use **type hints** wherever possible
- Write **docstrings** for all functions

```python
# ✅ Good
def calculate_recharge(pre_monsoon: float, post_monsoon: float) -> float:
    """
    Calculate net groundwater recharge between two seasonal readings.

    Args:
        pre_monsoon: Water level in meters before monsoon (May/June)
        post_monsoon: Water level in meters after monsoon (Oct/Nov)

    Returns:
        Net recharge in meters (positive = recharge, negative = depletion)
    """
    return pre_monsoon - post_monsoon


# ❌ Bad
def calc(a, b):
    return a - b
```

- Use `black` for formatting: `black app/`
- Use `flake8` for linting: `flake8 app/`

### JavaScript / React (Frontend)

- Use **functional components** with hooks
- Use **meaningful variable names**
- Keep components **small and focused** — one job per component
- Use **Tailwind CSS** for styling — no inline styles

```jsx
// ✅ Good
const StationCard = ({ station }) => {
  const status = getStatus(station.waterLevel);
  return (
    <div className="rounded-lg border p-4">
      <h3 className="font-bold">{station.name}</h3>
      <StatusBadge status={status} />
    </div>
  );
};

// ❌ Bad
const Card = ({ d }) => <div style={{borderRadius:'8px'}}>{d.n}</div>;
```

- Use `eslint` for linting: `npm run lint`
- Use `prettier` for formatting: `npm run format`

---

## 💬 Commit Message Guidelines

We follow the **Conventional Commits** standard:

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Types:**

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructure, no new feature |
| `test` | Adding or fixing tests |
| `chore` | Build process, dependencies |

**Examples:**

```bash
feat(backend): add Task 2 recharge estimation algorithm
fix(map): resolve station dots not rendering on mobile
docs(api): add endpoint documentation for /api/task3
test(services): add unit tests for fluctuation analysis
chore(deps): update FastAPI to 0.104.1
```

---

## 🔍 Pull Request Process

1. **Fill out the PR template** completely
2. **Link the related issue** using `Closes #issue_number`
3. **Make sure all CI checks pass** — tests, linting
4. **Add screenshots** for any UI changes
5. **Request a review** from a maintainer
6. **Address all review comments** before merging

### PR Title Format

Follow the same convention as commits:

```
feat(dashboard): add district-level groundwater scorecard
fix(api): handle missing station data gracefully
```

---

## 🐛 Reporting Bugs

Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:

- **What you expected** to happen
- **What actually happened**
- **Steps to reproduce** the bug
- **Your environment** (OS, Python version, Node version)
- **Screenshots** if applicable

---

## ✨ Suggesting Features

Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md) and include:

- **What problem** does this feature solve?
- **Who benefits** from it?
- **How would it work?** (rough idea is fine)
- **Any alternatives** you considered?

---

## 🏷️ Issue Labels

| Label | Meaning |
|-------|---------|
| `good first issue` | Great for new contributors |
| `help wanted` | Extra attention needed |
| `bug` | Something is broken |
| `enhancement` | New feature or improvement |
| `documentation` | Docs need updating |
| `data` | Related to data sources |
| `backend` | Backend / API related |
| `frontend` | UI / dashboard related |

---

## ❓ Need Help?

- Open a **Discussion** on GitHub
- Comment on the relevant **Issue**
- Read [docs/setup-guide.md](./docs/setup-guide.md) for setup help

---

<div align="center">
Thank you for contributing to SubTerra 💧
<br/>
Together we can make India's groundwater data accessible to everyone.
</div>
