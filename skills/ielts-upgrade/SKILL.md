---
name: ielts-upgrade
description: Upgrade IELTS Claude Teacher to the latest version from GitHub.
  Safely pulls latest code while preserving all learning data (.ielts/, .env, custom mods).
triggers:
  - upgrade ielts
  - update ielts
  - nâng cấp ielts
  - cập nhật ielts
  - ielts upgrade
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# /ielts-upgrade

Upgrade dự án IELTS Claude Teacher lên version mới nhất từ GitHub,
bảo toàn toàn bộ dữ liệu học tập.

## Khi nào dùng

- Có version mới trên GitHub (`https://github.com/chauvanphuoc/ielts-claude-teacher`)
- Muốn cập nhật skill mới, bug fixes, feature enhancements
- Được thông báo "Upgrade available"

## Nguyên tắc

1. **Data first** — `.ielts/` và `.env` đã gitignored, không bị ảnh hưởng bởi git operations. Vẫn backup trước khi upgrade để an toàn tuyệt đối.
2. **Non-destructive** — git stash bảo vệ local modifications, git reflog cho phép rollback.
3. **Transparent** — hiển thị CHANGELOG sau upgrade để user biết có gì mới.
4. **Idempotent** — chạy upgrade nhiều lần không gây lỗi.

---

## Upgrade Flow

### Step 1 — Pre-flight Checks

```bash
# Xác nhận đây là git repo của ielts-claude-teacher
if [ ! -d ".git" ]; then
  echo "ERROR: Không tìm thấy .git — đây không phải là git repo."
  echo "Vui lòng clone từ https://github.com/chauvanphuoc/ielts-claude-teacher"
  exit 1
fi

REMOTE_URL=$(git remote get-url origin 2>/dev/null)
if ! echo "$REMOTE_URL" | grep -q "chauvanphuoc/ielts-claude-teacher"; then
  echo "WARNING: Remote origin không phải là chauvanphuoc/ielts-claude-teacher"
  echo "Remote hiện tại: $REMOTE_URL"
  echo "Tiếp tục? (có thể không an toàn)"
fi

OLD_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
echo "Current version: $OLD_VERSION"
```

### Step 2 — Confirm with User

Hiển thị thông tin trước khi upgrade:

> **IELTS Claude Teacher Upgrade**
>
> - Current version: v{OLD_VERSION}
> - Remote: {REMOTE_URL}
> - Data backup: `.ielts/` → `.ielts.bak/`
>
> Upgrade sẽ:
> 1. Backup toàn bộ dữ liệu học tập
> 2. Fetch code mới nhất từ GitHub
> 3. Chạy migrations (nếu có)
> 4. Rebuild Python environment (nếu cần)
>
> Tiếp tục?

Nếu user đồng ý → Step 3.

### Step 3 — Backup User Data

```bash
echo "=== Backing up user data ==="

# Backup .ielts/
if [ -d ".ielts" ]; then
  rm -rf .ielts.bak 2>/dev/null
  cp -r .ielts .ielts.bak
  echo "✓ .ielts/ → .ielts.bak/"
fi

# Backup .env
if [ -f ".env" ]; then
  cp .env .env.bak
  echo "✓ .env → .env.bak"
fi

# Stash local modifications
STASH_OUTPUT=$(git stash 2>&1)
STASHED=false
if ! echo "$STASH_OUTPUT" | grep -q "No local changes"; then
  STASHED=true
  echo "✓ Local modifications stashed"
else
  echo "  (no local modifications found)"
fi
```

### Step 4 — Fetch Latest Code

```bash
echo "=== Fetching latest code ==="

# Fetch từ GitHub
if ! git fetch origin 2>&1; then
  echo "ERROR: Không thể fetch từ GitHub. Kiểm tra kết nối internet."
  echo "Rolling back..."
  [ -d ".ielts.bak" ] && rm -rf .ielts .ielts.bak-backup 2>/dev/null
  exit 1
fi

# Get latest
git reset --hard origin/main 2>&1
echo "✓ Code updated to latest origin/main"
```

### Step 5 — Run Migrations

```bash
echo "=== Running migrations ==="

MIGRATIONS_DIR="skills/ielts-teacher/migrations"

if [ -d "$MIGRATIONS_DIR" ]; then
  for migration in $(find "$MIGRATIONS_DIR" -maxdepth 1 -name 'v*.sh' -type f 2>/dev/null | sort -V); do
    m_ver=$(basename "$migration" .sh | sed 's/^v//')
    # Run if migration version > old version
    if [ "$OLD_VERSION" != "unknown" ] && [ "$(printf '%s\n%s' "$OLD_VERSION" "$m_ver" | sort -V | head -1)" = "$OLD_VERSION" ] && [ "$OLD_VERSION" != "$m_ver" ]; then
      echo "Running migration $m_ver..."
      bash "$migration" || echo "  ⚠ Warning: migration $m_ver had errors (non-fatal, continuing)"
    fi
  done
fi
echo "✓ Migrations complete"
```

### Step 6 — Rebuild Environment (if needed)

```bash
echo "=== Checking Python environment ==="

# Check if .venv exists and is functional
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/python3" ]; then
  echo "Creating .venv..."
  python3 -m venv .venv
  echo "✓ .venv created"
fi

# Check if key packages are installed
if ! .venv/bin/python3 -c "import flask" 2>/dev/null; then
  echo "Installing dependencies..."
  .venv/bin/pip install flask 2>&1 | tail -1
  echo "✓ Dependencies installed"
else
  echo "✓ Python environment OK"
fi
```

### Step 7 — Restore User Data

```bash
echo "=== Restoring user data ==="

# Restore .ielts/ nếu backup tồn tại và .ielts/ bị mất
if [ -d ".ielts.bak" ] && [ ! -d ".ielts" ]; then
  cp -r .ielts.bak .ielts
  echo "✓ .ielts/ restored from backup"
fi

# Clean up backup (user data confirmed safe by gitignore)
if [ -d ".ielts.bak" ]; then
  rm -rf .ielts.bak
  echo "✓ Backup cleaned up"
fi

if [ -f ".env.bak" ] && [ ! -f ".env" ]; then
  mv .env.bak .env
  echo "✓ .env restored from backup"
fi

# Restore stashed changes
if [ "$STASHED" = "true" ]; then
  if ! git stash pop 2>&1; then
    echo "⚠ Có conflicts khi restore local modifications."
    echo "Xem git stash list và resolve thủ công."
    echo "Code mới đã được áp dụng — conflicts nằm trong unstaged changes."
  else
    echo "✓ Local modifications restored"
  fi
fi
```

### Step 8 — Verify & Show Changelog

```bash
echo "=== Post-upgrade verification ==="

# Đọc version mới
NEW_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
echo "Upgraded: v$OLD_VERSION → v$NEW_VERSION"

# Run validation
if [ -f "shared/ielts_cli.py" ]; then
  .venv/bin/python3 shared/ielts_cli.py validate 2>&1 || echo "⚠ Validation warnings (non-fatal)"
fi
```

**Show CHANGELOG:**

Đọc `CHANGELOG.md`. Tìm tất cả version entries giữa OLD_VERSION và NEW_VERSION. Tóm tắt thành 5-7 bullet points, nhóm theo theme:

```
✅ IELTS Claude Teacher v{NEW_VERSION} — upgraded from v{OLD_VERSION}!

What's new:
- [feature/bug fix 1]
- [feature/bug fix 2]
- ...

Full changelog: CHANGELOG.md
```

---

## Rollback (nếu cần)

Nếu upgrade gây lỗi, có thể rollback:

```bash
# Cách 1: Git reflog
git reflog                    # Tìm commit trước upgrade
git reset --hard HEAD@{1}     # Quay lại commit cũ

# Cách 2: Restore từ backup
cp -r .ielts.bak .ielts       # Restore dữ liệu (nếu backup chưa bị xóa)
```

---

## Safety Checklist

Trước khi upgrade, Claude sẽ kiểm tra:
- [ ] Working directory là git repo của `chauvanphuoc/ielts-claude-teacher`
- [ ] Có kết nối internet (fetch được GitHub)
- [ ] `.ielts/` tồn tại (có dữ liệu để backup)
- [ ] User được hỏi và đồng ý trước khi upgrade
