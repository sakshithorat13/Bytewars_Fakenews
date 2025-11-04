# Veritas Deployment Guide - Render

## Quick Deployment Steps

### 1. Create Render Account
- Go to [render.com](https://render.com)
- Sign up with your GitHub account

### 2. Connect Repository
- Click "New Web Service"
- Connect your GitHub repository: `sakshithorat13/Bytewars_Fakenews`
- Select the repository

### 3. Configure Service
- **Name**: `veritas-backend`
- **Root Directory**: `veritas-backend`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 4. Set Environment Variables
Add these environment variables in Render dashboard:
- `GEMINI_API_KEY`: `AIzaSyBkxtiZj_6XUCU0bcz3xFWmaanct9kvXvY`
- `PORT`: `10000` (Render will set this automatically)
- `DEBUG`: `False`

### 5. Deploy
- Click "Create Web Service"
- Wait for deployment (5-10 minutes)
- Copy the provided URL (e.g., `https://veritas-backend.onrender.com`)

### 6. Update Flutter App
- Update `lib/services/api_service.dart`
- Replace `http://192.168.1.26:8001` with your Render URL

### 7. Test
- Your backend will be live at: `https://your-app-name.onrender.com`
- Health check: `https://your-app-name.onrender.com/health`

## Alternative: One-Click Deploy

You can also use the render.yaml file included in this repo for automatic deployment configuration.