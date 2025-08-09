# Environment Variables Setup Guide

## 🚨 IMPORTANT: Secret Management

This guide explains how to properly manage environment variables and API keys in your Alchemize project.

## Problem Solved

Your Git push was failing because GitHub's secret scanning detected real API keys in your commit history. This has been resolved by:

1. ✅ Creating a clean Git history without any exposed secrets
2. ✅ Replacing real API keys with placeholders in `.env` file
3. ✅ Successfully pushing to GitHub

## Environment Files Overview

Your project uses multiple environment files for different purposes:

### 1. `.env` (Main Development File)
- **Location**: Root directory
- **Purpose**: Local development configuration
- **Status**: ✅ Already exists with placeholder values
- **Git Status**: Ignored (never committed)

### 2. `.env.example` (Template File)
- **Location**: Root directory  
- **Purpose**: Template showing required environment variables
- **Status**: ✅ Committed to Git (safe - contains no real secrets)

### 3. `.env.sample` (Alternative Template)
- **Location**: Root directory
- **Purpose**: Another template file
- **Status**: ✅ Committed to Git (safe)

### 4. `.env.local` (Optional Override)
- **Location**: Root directory
- **Purpose**: Local overrides (loaded first if exists)
- **Git Status**: Ignored

### 5. `.env.production` (Production File)
- **Location**: Root directory
- **Purpose**: Production environment variables
- **Git Status**: Ignored

## 🔑 Setting Up Your API Keys

### Step 1: Edit Your `.env` File

Open `C:\Users\merli\OneDrive\Desktop\Alchemize\.env` and replace these placeholder values:

```bash
# Replace this placeholder with your actual OpenAI API key
OPENAI_API_KEY=sk-your-openai-api-key-here

# Replace with your actual Firebase credentials
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"your-project-id"}
FIREBASE_STORAGE_BUCKET=gs://your-bucket-name.firebasestorage.appspot.com

# Update other keys as needed
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key_here
```

### Step 2: Get Your API Keys

#### OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in to your account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)
5. Replace `sk-your-openai-api-key-here` in your `.env` file

#### Firebase Credentials (if using Firebase)
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to Project Settings > Service Accounts
4. Generate new private key
5. Download the JSON file
6. Copy the JSON content to `FIREBASE_CREDENTIALS_JSON`

#### Stripe Keys (if using payments)
1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Go to Developers > API Keys
3. Copy your publishable and secret keys
4. Update the values in your `.env` file

## 🛡️ Security Best Practices

### ✅ DO:
- Keep real API keys only in `.env` files (never committed)
- Use placeholder values in `.env.example`
- Regularly rotate your API keys
- Use different keys for development and production
- Set proper file permissions on `.env` files

### ❌ DON'T:
- Never commit `.env` files with real secrets
- Never hardcode API keys in source code
- Never share API keys in chat/email
- Never use production keys in development

## 🔄 Git Workflow After Setup

Now that your repository is clean, you can safely use Git:

```bash
# Make your code changes (not .env files)
git add .
git commit -m "Your commit message"
git push
```

**Note**: The `.env` file is in `.gitignore`, so your real API keys will never be committed.

## 🚀 Running the Application

After setting up your API keys:

1. **Backend**: `python -m uvicorn app.main:app --reload --port 8001`
2. **Frontend**: `cd web && npm run dev`
3. **Celery Worker**: `celery -A app.celery_app worker --loglevel=info`

## 🆘 Troubleshooting

### If you get "API key not found" errors:
1. Check that your `.env` file exists in the root directory
2. Verify the API key format (OpenAI keys start with `sk-`)
3. Ensure no extra spaces around the `=` sign
4. Restart your application after changing `.env`

### If Git push fails again:
1. Make sure you're not committing any `.env` files
2. Check that no API keys are hardcoded in your source code
3. Use `git status` to see what files are being committed

## 📁 File Structure Summary

```
Alchemize/
├── .env                 # Your real API keys (NEVER commit)
├── .env.example         # Template (safe to commit)
├── .env.sample          # Another template (safe to commit)
├── .gitignore           # Contains .env (prevents commits)
└── ENVIRONMENT_SETUP_GUIDE.md  # This guide
```

## ✅ Status Check

- [x] Git repository cleaned of all secrets
- [x] Clean commit history established
- [x] `.env` file exists with placeholder values
- [x] `.gitignore` properly configured
- [x] Successfully pushed to GitHub
- [ ] **TODO**: Replace placeholder API keys with your real keys
- [ ] **TODO**: Test application with real API keys

---

**Remember**: Your `.env` file with real API keys should never be committed to Git. The current setup ensures this won't happen accidentally.