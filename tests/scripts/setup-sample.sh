cd "$(dirname "$0")/../fixtures/sample-workspace"
if [ ! -d .git ]; then
    git init
    git config user.email "test@example.com"
    git config user.name "Test User"
    git add .
    git commit -m "Initial commit"

    # Make a second commit by modifying README
    echo "" >> README.md
    echo "Modified for testing" >> README.md
    git add README.md
    git commit -m "Update README"
fi
