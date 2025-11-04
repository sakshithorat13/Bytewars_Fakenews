# Veritas Deployment Guide - Vercel (Even Easier!)

## Super Quick Deployment Steps

### 1. Install Vercel CLI
```bash
npm install -g vercel
```

### 2. Deploy (One Command!)
```bash
cd "C:\Users\HP\Desktop\Bytewars_Fakenews\bytewars_fakenews"
vercel --prod
```

### 3. Follow Prompts
- Login to Vercel (creates account if needed)
- Confirm project settings
- Add environment variable when prompted:
  - `GEMINI_API_KEY`: `AIzaSyBkxtiZj_6XUCU0bcz3xFWmaanct9kvXvY`

### 4. Copy URL
- Vercel will give you a URL like: `https://bytewars-fakenews.vercel.app`

### 5. Update Flutter App
- Update `lib/services/api_service.dart`
- Replace `http://192.168.1.26:8001` with your Vercel URL

## That's it! 🎉

Your app will be live in under 2 minutes!