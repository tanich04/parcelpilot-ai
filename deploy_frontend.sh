#!/bin/bash
# deploy_frontend.sh

echo "🚀 Deploying ParcelPilot Frontend to Streamlit Cloud..."
echo ""

echo "📋 Steps:"
echo "1. Push code to GitHub"
echo "2. Go to https://share.streamlit.io"
echo "3. Click 'New app'"
echo "4. Connect your GitHub repository"
echo "5. Set these settings:"
echo "   - Repository: yourusername/parcelpilot-ai"
echo "   - Branch: main"
echo "   - Main file: src/ui/streamlit_app.py"
echo "6. Add environment variable:"
echo "   - API_BASE_URL: https://parcelpilot-api.onrender.com"
echo "7. Click 'Deploy'"