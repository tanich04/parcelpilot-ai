#!/bin/bash
# deploy_backend.sh - Deploy ParcelPilot Backend to Render

echo "🚀 Deploying ParcelPilot Backend to Render..."
echo ""

# Check if render.yaml exists
if [ ! -f "render.yaml" ]; then
    echo "❌ render.yaml not found!"
    echo "   Make sure render.yaml is in the root directory."
    exit 1
fi

echo "✅ render.yaml found"

# Check if .env has GROQ_API_KEY
if [ -f ".env" ]; then
    source .env
    if [ -n "$GROQ_API_KEY" ]; then
        echo "✅ GROQ_API_KEY found in .env"
    else
        echo "⚠️  GROQ_API_KEY not set in .env"
    fi
else
    echo "⚠️  .env file not found"
fi

echo ""
echo "📋 Deployment Options:"
echo ""
echo "Option 1: Deploy via Render Dashboard (Recommended)"
echo "  1. Go to https://dashboard.render.com"
echo "  2. Click 'New +' → 'Web Service'"
echo "  3. Connect your GitHub repository"
echo "  4. Render will auto-detect render.yaml"
echo "  5. Add environment variable:"
echo "     - GROQ_API_KEY: your_groq_api_key"
echo "  6. Click 'Create Web Service'"
echo ""
echo "Option 2: Deploy via Render CLI"
echo "  brew install render-cli  # Mac"
echo "  render deploy --service parcelpilot-api"
echo ""
echo "Option 3: Deploy via GitHub Actions"
echo "  Push to main branch → Auto-deploy"
echo ""

# Check if git is initialized
if [ -d ".git" ]; then
    echo "📦 Current Git Status:"
    git status --short
    echo ""
    echo "To push changes:"
    echo "  git add ."
    echo "  git commit -m 'Deploy ParcelPilot API'"
    echo "  git push origin main"
else
    echo "⚠️  Git not initialized. Run:"
    echo "  git init"
    echo "  git add ."
    echo "  git commit -m 'Initial commit'"
    echo "  git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git"
    echo "  git push -u origin main"
fi

echo ""
echo "✅ After deployment, your API will be available at:"
echo "   https://parcelpilot-api.onrender.com"
echo "   API Docs: https://parcelpilot-api.onrender.com/docs"
echo ""
echo "🔗 Don't forget to set API_BASE_URL in Streamlit Cloud secrets:"
echo "   API_BASE_URL = https://parcelpilot-api.onrender.com"
