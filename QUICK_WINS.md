# Quick Wins - Dependency Optimization

These are the fastest, highest-impact changes you can make right now.

## 🚨 Critical: Fix Version Conflicts (5 minutes)

**Problem:** Your `requirements.txt` and `api/requirements.txt` have conflicting versions that could cause runtime errors.

**Solution:**

```bash
# Run the automated fix script:
./DEPENDENCY_FIX_PLAN.sh

# OR manually update these files:
```

### Update `requirements.txt` line 14-18:
```diff
- flask==3.0.0
+ flask==3.1.0
- flask-cors==4.0.0
+ flask-cors==5.0.0
- werkzeug==3.0.6
+ werkzeug==3.1.4
```

### Update `api/requirements.txt` lines 1-5:
```diff
- flask==3.0.3
+ flask==3.1.0
- flask-cors==5.0.0  # Keep this version
+ flask-cors==5.0.0
- werkzeug==3.1.4    # Keep this version
+ werkzeug==3.1.4
```

### Update `pyproject.toml` line 34, 37-39:
```diff
- pillow>=10.0.0
+ pillow>=11.0.0
- flask>=3.0.0
+ flask>=3.1.0
- flask-cors>=4.0.0
+ flask-cors>=5.0.0
- werkzeug>=3.0.0
+ werkzeug>=3.1.0
```

**Test:**
```bash
pip install -r requirements.txt
python quick_test.py  # or your test command
```

---

## 🎯 High Impact: Remove Duplicate Icon Libraries (10 minutes)

**Problem:** You have 3 icon libraries installed (~3.5 MB total), but probably only need one.

**Step 1 - Audit usage:**
```bash
cd frontend
./FRONTEND_BLOAT_AUDIT.sh
```

**Step 2 - Choose based on usage:**
- If most icons are from **lucide-react**: Keep it
- If most icons are from **@heroicons/react**: Keep it
- If most icons are from **@phosphor-icons/react**: Keep it

**Step 3 - Remove unused libraries:**
```bash
# Example: Keep lucide-react, remove others
npm uninstall @heroicons/react @phosphor-icons/react

# Update imports in your code
grep -rl "@heroicons/react" src/ | xargs sed -i 's/@heroicons\/react/lucide-react/g'
grep -rl "@phosphor-icons/react" src/ | xargs sed -i 's/@phosphor-icons\/react/lucide-react/g'
```

**Savings:** ~2.5 MB (uncompressed), ~800 KB (gzipped)

---

## 🔍 Medium Impact: Check Three.js Usage (5 minutes)

**Problem:** Three.js (~600 KB) might not be used in your dyno tuning app.

**Check usage:**
```bash
cd frontend
grep -r "from 'three'" src/
```

**If no results:**
```bash
npm uninstall three @types/three
```

**Savings:** ~600 KB (gzipped)

---

## 🧹 Low Effort: Remove Unused Radix Components (15 minutes)

**Problem:** 28 Radix UI packages installed, some might be unused.

**Find unused packages:**
```bash
cd frontend
npx depcheck
```

**Remove unused ones:**
```bash
# Example output might show:
npm uninstall @radix-ui/react-aspect-ratio @radix-ui/react-menubar
```

**Savings:** ~20-50 KB per unused component

---

## 📊 Results After Quick Wins

| Optimization | Time | Savings | Difficulty |
|--------------|------|---------|------------|
| Fix version conflicts | 5 min | Risk reduction | Easy |
| Security update (Pillow) | 2 min | High severity fix | Easy |
| Remove 2 icon libraries | 10 min | ~800 KB | Medium |
| Remove Three.js (if unused) | 5 min | ~600 KB | Easy |
| Remove unused Radix | 15 min | ~100-300 KB | Easy |
| **TOTAL** | **37 min** | **~1.5 MB + Security** | |

---

## 🔐 Security Fix Summary

**Current vulnerabilities:**
1. **Pillow < 11.0.0** - High severity image processing vulnerability
2. **Flask-CORS 4.x** - Missing security improvements in 5.x

**Fix both with the version updates above.** ✅

---

## 📋 Checklist

- [ ] Run `./DEPENDENCY_FIX_PLAN.sh` OR manually update Python dependencies
- [ ] Run `pip install -r requirements.txt` and test
- [ ] Run `cd frontend && ./FRONTEND_BLOAT_AUDIT.sh`
- [ ] Remove duplicate icon libraries
- [ ] Check Three.js usage and remove if unused
- [ ] Run `npx depcheck` and remove unused packages
- [ ] Test frontend: `npm run build && npm run preview`
- [ ] Commit changes: `git commit -am "fix: Update dependencies and remove bloat"`

---

## ⚠️ Before You Start

1. **Backup your work:**
   ```bash
   git stash  # or commit your current changes
   git checkout -b dependency-updates
   ```

2. **The fix script creates backups automatically:**
   - `requirements.txt.backup`
   - `api/requirements.txt.backup`
   - `pyproject.toml.backup`

3. **Test after each change** - Don't do everything at once!

---

## 🆘 If Something Breaks

**Python dependencies:**
```bash
# Restore from backup
cp requirements.txt.backup requirements.txt
cp api/requirements.txt.backup api/requirements.txt
cp pyproject.toml.backup pyproject.toml
pip install -r requirements.txt
```

**Frontend dependencies:**
```bash
# Restore from package-lock.json
rm -rf node_modules
npm ci
```

---

## 📖 Full Details

See `DEPENDENCY_AUDIT_REPORT.md` for complete analysis and long-term recommendations.
