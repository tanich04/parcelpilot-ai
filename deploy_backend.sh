#!/bin/bash
# deploy_backend.sh

echo "🚀 Deploying ParcelPilot Backend to Render..."
echo ""

echo "📋 Steps:"
echo "1. Push code to GitHub"
echo "2. Go to https://dashboard.render.com"
echo "3. Click 'New +' and select 'Web Service'"
echo "4. Connect your GitHub repository"
echo "5. Use these settings:"
echo "   - Name: parcelpilot-api"
echo "   - Environment: Python 3"
echo "   - Build Command: pip install -r requirements.txt"
echo "   - Start Command: uvicorn src.api.endpoints:app --host 0.0.0.0 --port 10000"
echo "6. Add environment variable:"
echo "   - GROQ_API_KEY: your_groq_api_key"
echo "7. Click 'Create Web Service'"