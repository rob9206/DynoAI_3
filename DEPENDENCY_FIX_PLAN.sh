#!/bin/bash
# Dependency Fix Action Plan
# Generated: 2025-12-15
# Execute this script to implement Priority 1 fixes

set -e

echo "=================================================="
echo "DynoAI Dependency Fix Plan"
echo "=================================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# PRIORITY 1: Fix Python Version Conflicts
echo -e "${YELLOW}[Priority 1] Fixing Python version conflicts...${NC}"
echo ""

# Backup existing files
echo "Creating backups..."
cp requirements.txt requirements.txt.backup
cp api/requirements.txt api/requirements.txt.backup
cp pyproject.toml pyproject.toml.backup
echo -e "${GREEN}✓ Backups created${NC}"
echo ""

# Update requirements.txt
echo "Updating requirements.txt..."
cat > requirements.txt << 'EOF'
numpy==1.26.4
pandas==2.2.2
matplotlib==3.9.2
beautifulsoup4==4.12.3
requests==2.32.3
pillow==11.0.0
pytesseract==0.3.10
pyyaml==6.0.2
jsonschema==4.23.0
ruff==0.6.2
black==24.8.0
mypy==1.11.2
pre-commit==3.8.0
flask==3.1.0
flask-cors==5.0.0
Flask-Limiter>=3.5.0
flasgger>=0.9.7
werkzeug==3.1.4
python-dotenv==1.0.0
EOF
echo -e "${GREEN}✓ Updated requirements.txt${NC}"
echo ""

# Update api/requirements.txt
echo "Updating api/requirements.txt..."
cat > api/requirements.txt << 'EOF'
flask==3.1.0
flask-cors==5.0.0
flask-limiter>=3.5.0
flask-socketio>=5.3.0
werkzeug==3.1.4
python-dotenv==1.0.0
jsonschema==4.23.0
flasgger>=0.9.7
defusedxml>=0.7.1
eventlet>=0.33.0
EOF
echo -e "${GREEN}✓ Updated api/requirements.txt${NC}"
echo ""

# Update pyproject.toml
echo "Updating pyproject.toml..."
sed -i 's/pillow>=10.0.0/pillow>=11.0.0/' pyproject.toml
sed -i 's/flask>=3.0.0/flask>=3.1.0/' pyproject.toml
sed -i 's/flask-cors>=4.0.0/flask-cors>=5.0.0/' pyproject.toml
sed -i 's/werkzeug>=3.0.0/werkzeug>=3.1.0/' pyproject.toml
echo -e "${GREEN}✓ Updated pyproject.toml${NC}"
echo ""

# Reinstall packages
echo -e "${YELLOW}Reinstalling Python packages...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Python packages updated${NC}"
echo ""

# Verify installations
echo "Verifying package versions..."
echo "Flask: $(pip show flask | grep Version)"
echo "Flask-CORS: $(pip show flask-cors | grep Version)"
echo "Werkzeug: $(pip show werkzeug | grep Version)"
echo "Pillow: $(pip show pillow | grep Version)"
echo ""

# Run tests to ensure nothing broke
echo -e "${YELLOW}Running tests to verify updates...${NC}"
if [ -f "quick_test.py" ]; then
    python quick_test.py
    echo -e "${GREEN}✓ Tests passed${NC}"
else
    echo -e "${YELLOW}⚠ No quick_test.py found, skipping test verification${NC}"
fi
echo ""

echo "=================================================="
echo -e "${GREEN}Priority 1 fixes complete!${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Test your application thoroughly"
echo "2. Review DEPENDENCY_AUDIT_REPORT.md for Priority 2-4 items"
echo "3. Commit changes: git add requirements.txt api/requirements.txt pyproject.toml"
echo "4. Commit: git commit -m 'fix: Update dependencies to resolve conflicts and security issues'"
echo ""
echo "Backup files created:"
echo "  - requirements.txt.backup"
echo "  - api/requirements.txt.backup"
echo "  - pyproject.toml.backup"
echo ""
