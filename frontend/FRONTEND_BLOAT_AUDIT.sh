#!/bin/bash
# Frontend Dependency Bloat Audit Script
# Generated: 2025-12-15
# Run this script to identify unused dependencies and icon library usage

set -e

echo "=================================================="
echo "Frontend Dependency Bloat Audit"
echo "=================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$(dirname "$0")"

# Check if src directory exists
if [ ! -d "src" ]; then
    echo -e "${RED}Error: src directory not found${NC}"
    exit 1
fi

# AUDIT 1: Icon Library Usage
echo -e "${YELLOW}[1/5] Auditing Icon Library Usage...${NC}"
echo ""

echo "Lucide React usage:"
lucide_count=$(grep -r "from 'lucide-react'" src/ 2>/dev/null | wc -l)
echo "  Files using lucide-react: $lucide_count"

echo "Heroicons usage:"
heroicons_count=$(grep -r "from '@heroicons/react'" src/ 2>/dev/null | wc -l)
echo "  Files using @heroicons/react: $heroicons_count"

echo "Phosphor Icons usage:"
phosphor_count=$(grep -r "from '@phosphor-icons/react'" src/ 2>/dev/null | wc -l)
echo "  Files using @phosphor-icons/react: $phosphor_count"

echo ""
echo "Recommendation:"
if [ $lucide_count -gt $heroicons_count ] && [ $lucide_count -gt $phosphor_count ]; then
    echo -e "${GREEN}  → Keep lucide-react, remove others${NC}"
    echo "  → npm uninstall @heroicons/react @phosphor-icons/react"
elif [ $heroicons_count -gt $lucide_count ] && [ $heroicons_count -gt $phosphor_count ]; then
    echo -e "${GREEN}  → Keep @heroicons/react, remove others${NC}"
    echo "  → npm uninstall lucide-react @phosphor-icons/react"
else
    echo -e "${GREEN}  → Keep @phosphor-icons/react, remove others${NC}"
    echo "  → npm uninstall lucide-react @heroicons/react"
fi
echo ""

# AUDIT 2: Three.js Usage
echo -e "${YELLOW}[2/5] Auditing Three.js Usage...${NC}"
echo ""

three_imports=$(grep -r "from 'three'" src/ 2>/dev/null | wc -l)
three_files=$(grep -r "from 'three'" src/ 2>/dev/null | cut -d: -f1 | sort -u)

echo "Three.js usage:"
echo "  Import statements found: $three_imports"

if [ $three_imports -eq 0 ]; then
    echo -e "${RED}  ⚠ Three.js is NOT used - consider removing${NC}"
    echo "  → npm uninstall three @types/three"
    echo "  → Savings: ~600 KB"
else
    echo -e "${GREEN}  ✓ Three.js is in use:${NC}"
    echo "$three_files" | sed 's/^/    /'
fi
echo ""

# AUDIT 3: Radix UI Component Usage
echo -e "${YELLOW}[3/5] Auditing Radix UI Components...${NC}"
echo ""

radix_packages=$(cat package.json | grep "@radix-ui" | cut -d'"' -f2)
echo "Installed Radix UI packages: $(echo "$radix_packages" | wc -l)"
echo ""

unused_radix=()
for package in $radix_packages; do
    package_name=$(echo "$package" | sed 's/@radix-ui\/react-//')
    # Search for imports
    if ! grep -r "from '$package'" src/ > /dev/null 2>&1; then
        unused_radix+=("$package")
    fi
done

if [ ${#unused_radix[@]} -gt 0 ]; then
    echo -e "${RED}Potentially unused Radix UI components:${NC}"
    for pkg in "${unused_radix[@]}"; do
        echo "  - $pkg"
    done
    echo ""
    echo "To remove:"
    echo "  npm uninstall ${unused_radix[@]}"
    echo "  Estimated savings: $((${#unused_radix[@]} * 30)) KB"
else
    echo -e "${GREEN}✓ All Radix UI components appear to be in use${NC}"
fi
echo ""

# AUDIT 4: GitHub Library Usage
echo -e "${YELLOW}[4/5] Auditing GitHub Libraries...${NC}"
echo ""

octokit_core=$(grep -r "from '@octokit/core'" src/ 2>/dev/null | wc -l)
octokit=$(grep -r "from 'octokit'" src/ 2>/dev/null | wc -l)
github_spark=$(grep -r "from '@github/spark'" src/ 2>/dev/null | wc -l)

echo "GitHub library usage:"
echo "  @octokit/core: $octokit_core imports"
echo "  octokit: $octokit imports"
echo "  @github/spark: $github_spark imports"
echo ""

if [ $octokit_core -eq 0 ]; then
    echo -e "${RED}  ⚠ @octokit/core not used - remove it${NC}"
    echo "  → npm uninstall @octokit/core"
fi

if [ $octokit -eq 0 ]; then
    echo -e "${RED}  ⚠ octokit not used - remove it${NC}"
    echo "  → npm uninstall octokit"
fi

if [ $github_spark -eq 0 ]; then
    echo -e "${RED}  ⚠ @github/spark not used - remove it${NC}"
    echo "  → npm uninstall @github/spark"
fi

if [ $octokit_core -gt 0 ] && [ $octokit -gt 0 ]; then
    echo -e "${YELLOW}  ℹ Both @octokit/core and octokit are used${NC}"
    echo "  → Consider consolidating to just 'octokit'"
fi
echo ""

# AUDIT 5: HTTP Client Usage
echo -e "${YELLOW}[5/5] Auditing HTTP Client Usage...${NC}"
echo ""

axios_usage=$(grep -r "from 'axios'" src/ 2>/dev/null | wc -l)
fetch_usage=$(grep -r "\.fetch(" src/ 2>/dev/null | wc -l)

echo "HTTP client usage:"
echo "  axios imports: $axios_usage"
echo "  fetch() calls: $fetch_usage"
echo ""

if [ $axios_usage -eq 0 ]; then
    echo -e "${RED}  ⚠ Axios is not used - consider removing${NC}"
    echo "  → npm uninstall axios"
    echo "  → Use fetch API or React Query instead"
elif [ $axios_usage -lt 5 ] && [ $fetch_usage -gt 0 ]; then
    echo -e "${YELLOW}  ℹ Minimal axios usage detected${NC}"
    echo "  → Consider migrating to fetch API"
    echo "  → Axios usage found in:"
    grep -r "from 'axios'" src/ 2>/dev/null | cut -d: -f1 | sort -u | sed 's/^/    /'
else
    echo -e "${GREEN}  ✓ Axios is actively used${NC}"
fi
echo ""

# SUMMARY
echo "=================================================="
echo -e "${GREEN}Audit Complete!${NC}"
echo "=================================================="
echo ""
echo "Review the findings above and run the suggested commands."
echo ""
echo "To find ALL unused dependencies, install and run:"
echo "  npm install -g depcheck"
echo "  npx depcheck"
echo ""
echo "To analyze bundle size:"
echo "  npm run build"
echo "  npm install -g source-map-explorer"
echo "  source-map-explorer dist/**/*.js"
echo ""
