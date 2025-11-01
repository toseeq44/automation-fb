#!/bin/bash

# Git Conflict Resolution Script
# Run this on your local machine

echo "=========================================="
echo "Git Conflict Resolution"
echo "=========================================="

# Check current status
echo ""
echo "Current Status:"
git status

echo ""
echo "Choose an option:"
echo "1. Accept remote changes (discard local changes)"
echo "2. Keep local changes (reject remote changes)"
echo "3. Manually resolve conflicts"
echo ""
read -p "Enter choice (1/2/3): " choice

case $choice in
    1)
        echo ""
        echo "Accepting remote changes..."
        git fetch origin claude/license-system-implementation-011CUP8nmpPJ2rJTKUhYTun5
        git reset --hard origin/claude/license-system-implementation-011CUP8nmpPJ2rJTKUhYTun5
        echo "✅ Done! Remote changes accepted."
        git status
        ;;

    2)
        echo ""
        echo "Keeping local changes..."
        git add .
        git commit -m "Keeping local changes"
        git push -f origin claude/license-system-implementation-011CUP8nmpPJ2rJTKUhYTun5
        echo "✅ Done! Local changes kept."
        git status
        ;;

    3)
        echo ""
        echo "Manual resolution:"
        echo "1. Open conflicted files in editor"
        echo "2. Look for <<<<<<< HEAD markers"
        echo "3. Keep the code you want"
        echo "4. Delete conflict markers"
        echo "5. Run: git add ."
        echo "6. Run: git commit -m 'Resolved conflicts'"
        echo "7. Run: git push"
        ;;

    *)
        echo "Invalid choice!"
        ;;
esac
