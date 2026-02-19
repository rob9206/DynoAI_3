#!/bin/bash
# scan-large-blobs.sh - Efficient blob size scanner for Git repositories
# Reports large blobs and supports incremental scanning for PRs

set -euo pipefail

# Configuration
TOP_N=30
WARN_THRESHOLD_MB=50
FAIL_THRESHOLD_MB=90
REPORT_THRESHOLD_MB=25
OUTPUT_JSON="${OUTPUT_JSON:-blob_report.json}"

# Convert MB to bytes
WARN_THRESHOLD=$((WARN_THRESHOLD_MB * 1024 * 1024))
FAIL_THRESHOLD=$((FAIL_THRESHOLD_MB * 1024 * 1024))
REPORT_THRESHOLD=$((REPORT_THRESHOLD_MB * 1024 * 1024))

# Colors for terminal output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to format bytes to human-readable size
format_size() {
    local bytes=$1
    if [ "$bytes" -ge 1073741824 ]; then
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1073741824}")GB"
    elif [ "$bytes" -ge 1048576 ]; then
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1048576}")MB"
    elif [ "$bytes" -ge 1024 ]; then
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1024}")KB"
    else
        echo "${bytes}B"
    fi
}

# Function to find the commit that introduced a blob
find_introducing_commit() {
    local blob_sha=$1
    local path=$2
    
    # Find the earliest commit that introduced this blob at this path
    git log --all --pretty=format:'%h' --diff-filter=A -- "$path" | tail -1 || echo "unknown"
}

# Function to scan blobs in a revision range
scan_blobs() {
    local rev_range="${1:---all}"
    
    echo "Scanning blobs in range: $rev_range" >&2
    
    # Get all blobs with their sizes and paths
    git rev-list --objects $rev_range | \
    git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
    awk '/^blob/ {print $2, $3, $4}' | \
    while read -r sha size path; do
        # Skip if no path (dangling blob)
        if [ -z "$path" ]; then
            continue
        fi
        echo "$size $sha $path"
    done | sort -rn
}

# Function to get new blobs in PR (differential scan)
get_pr_new_blobs() {
    local base_ref="${1:-origin/main}"
    local head_ref="${2:-HEAD}"
    
    echo "Comparing $base_ref to $head_ref for new blobs..." >&2
    
    # Get all objects in head with paths (cache this)
    local head_objects=$(mktemp)
    git rev-list --objects "$head_ref" > "$head_objects"
    
    # Get blobs in head but not in base
    comm -13 \
        <(git rev-list --objects "$base_ref" | awk '{print $1}' | sort) \
        <(awk '{print $1}' "$head_objects" | sort) | \
    while read -r obj; do
        # Check if it's a blob and get its path
        if git cat-file -t "$obj" 2>/dev/null | grep -q "^blob$"; then
            # Get path from cached head_objects
            path=$(grep "^$obj " "$head_objects" | cut -d' ' -f2-)
            if [ -n "$path" ]; then
                size=$(git cat-file -s "$obj")
                echo "$size $obj $path"
            fi
        fi
    done | sort -rn
    
    # Cleanup
    rm -f "$head_objects"
}

# Main scanning logic
main() {
    local mode="${1:-full}"
    local base_ref="${2:-}"
    local head_ref="${3:-HEAD}"
    
    echo "Blob Risk Scanner"
    echo "================="
    echo ""
    
    # Determine scanning mode
    local blob_list
    if [ "$mode" = "pr" ] && [ -n "$base_ref" ]; then
        echo "Mode: PR differential scan"
        echo "Base: $base_ref"
        echo "Head: $head_ref"
        echo ""
        blob_list=$(get_pr_new_blobs "$base_ref" "$head_ref")
    else
        echo "Mode: Full repository scan"
        echo ""
        blob_list=$(scan_blobs --all)
    fi
    
    # Count total blobs
    local total_count=$(echo "$blob_list" | grep -c . || echo 0)
    echo "Total blobs found: $total_count"
    echo ""
    
    # Arrays for JSON output
    declare -a all_blobs=()
    declare -a large_blobs=()
    declare -a warning_blobs=()
    declare -a fail_blobs=()
    
    # Track risk levels
    local has_failures=0
    local has_warnings=0
    
    # Process top N blobs
    local count=0
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        
        read -r size sha path <<< "$line"
        
        count=$((count + 1))
        if [ $count -gt $TOP_N ]; then
            break
        fi
        
        # Find introducing commit
        local commit=$(find_introducing_commit "$sha" "$path")
        local formatted_size=$(format_size "$size")
        
        # Determine risk level
        local risk_level="info"
        local color=$GREEN
        
        if [ "$size" -ge "$FAIL_THRESHOLD" ]; then
            risk_level="fail"
            color=$RED
            has_failures=1
            fail_blobs+=("{\"size\":$size,\"path\":\"$path\",\"sha\":\"$sha\",\"commit\":\"$commit\",\"formatted_size\":\"$formatted_size\"}")
        elif [ "$size" -ge "$WARN_THRESHOLD" ]; then
            risk_level="warning"
            color=$YELLOW
            has_warnings=1
            warning_blobs+=("{\"size\":$size,\"path\":\"$path\",\"sha\":\"$sha\",\"commit\":\"$commit\",\"formatted_size\":\"$formatted_size\"}")
        fi
        
        # Add to large blobs if over report threshold
        if [ "$size" -ge "$REPORT_THRESHOLD" ]; then
            large_blobs+=("{\"size\":$size,\"path\":\"$path\",\"sha\":\"$sha\",\"commit\":\"$commit\",\"formatted_size\":\"$formatted_size\",\"risk_level\":\"$risk_level\"}")
        fi
        
        # Add to all blobs
        all_blobs+=("{\"size\":$size,\"path\":\"$path\",\"sha\":\"$sha\",\"commit\":\"$commit\",\"formatted_size\":\"$formatted_size\",\"risk_level\":\"$risk_level\"}")
        
        # Print to console
        printf "${color}%-10s %-10s %-10s %s${NC}\n" "$formatted_size" "$commit" "$risk_level" "$path"
    done <<< "$blob_list"
    
    echo ""
    echo "Summary:"
    echo "--------"
    echo "Total blobs scanned: $total_count"
    echo "Large blobs (>=${REPORT_THRESHOLD_MB}MB): ${#large_blobs[@]}"
    echo "Warning blobs (>=${WARN_THRESHOLD_MB}MB): ${#warning_blobs[@]}"
    echo "Fail blobs (>=${FAIL_THRESHOLD_MB}MB): ${#fail_blobs[@]}"
    
    # Generate JSON report
    generate_json_report "$mode" "$has_failures" "$has_warnings"
    
    # Exit with appropriate code
    if [ $has_failures -eq 1 ]; then
        echo ""
        echo -e "${RED}FAILURE: Blobs >= ${FAIL_THRESHOLD_MB}MB detected!${NC}"
        exit 1
    elif [ $has_warnings -eq 1 ]; then
        echo ""
        echo -e "${YELLOW}WARNING: Blobs >= ${WARN_THRESHOLD_MB}MB detected${NC}"
        exit 0
    else
        echo ""
        echo -e "${GREEN}SUCCESS: No large blobs detected${NC}"
        exit 0
    fi
}

# Function to generate JSON report
generate_json_report() {
    local mode=$1
    local has_failures=$2
    local has_warnings=$3
    
    # Determine status
    local status="success"
    if [ $has_failures -eq 1 ]; then
        status="failure"
    elif [ $has_warnings -eq 1 ]; then
        status="warning"
    fi
    
    # Build JSON arrays
    local all_blobs_json=$(IFS=,; echo "[${all_blobs[*]:-}]")
    local large_blobs_json=$(IFS=,; echo "[${large_blobs[*]:-}]")
    local warning_blobs_json=$(IFS=,; echo "[${warning_blobs[*]:-}]")
    local fail_blobs_json=$(IFS=,; echo "[${fail_blobs[*]:-}]")
    
    # Create JSON report
    cat > "$OUTPUT_JSON" <<EOF
{
  "scan_mode": "$mode",
  "status": "$status",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "thresholds": {
    "report_mb": $REPORT_THRESHOLD_MB,
    "warn_mb": $WARN_THRESHOLD_MB,
    "fail_mb": $FAIL_THRESHOLD_MB
  },
  "summary": {
    "total_blobs": ${#all_blobs[@]},
    "large_blobs": ${#large_blobs[@]},
    "warning_blobs": ${#warning_blobs[@]},
    "fail_blobs": ${#fail_blobs[@]}
  },
  "top_blobs": $all_blobs_json,
  "large_blobs": $large_blobs_json,
  "warning_blobs": $warning_blobs_json,
  "fail_blobs": $fail_blobs_json
}
EOF
    
    echo ""
    echo "JSON report written to: $OUTPUT_JSON"
}

# Parse command line arguments
MODE="full"
BASE_REF=""
HEAD_REF="HEAD"

while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --base)
            BASE_REF="$2"
            shift 2
            ;;
        --head)
            HEAD_REF="$2"
            shift 2
            ;;
        --output)
            OUTPUT_JSON="$2"
            shift 2
            ;;
        --help)
            cat <<HELP
Usage: $0 [OPTIONS]

Options:
  --mode <full|pr>     Scan mode (default: full)
  --base <ref>         Base reference for PR mode (e.g., origin/main)
  --head <ref>         Head reference for PR mode (default: HEAD)
  --output <file>      Output JSON file (default: blob_report.json)
  --help               Show this help message

Environment Variables:
  OUTPUT_JSON          Override default output file path

Examples:
  # Full repository scan
  $0

  # PR differential scan
  $0 --mode pr --base origin/main --head HEAD

  # Custom output location
  $0 --output /tmp/blob-report.json
HELP
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main "$MODE" "$BASE_REF" "$HEAD_REF"
