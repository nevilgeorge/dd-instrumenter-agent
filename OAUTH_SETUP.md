# GitHub OAuth Setup Guide

This guide will help you set up GitHub OAuth for the DD Instrumenter Agent to access private repositories.

## 1. Create a GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in the application details:
   - **Application name**: `DD Instrumenter Agent` (or your preferred name)
   - **Homepage URL**: `http://127.0.0.1:8000`
   - **Authorization callback URL**: `http://127.0.0.1:8000/auth/github/callback`
4. Click "Register application"
5. Copy the **Client ID** and **Client Secret**

## 2. Configure Environment Variables

Add the following to your `.env` file:

```bash
# GitHub OAuth Configuration
GITHUB_CLIENT_ID=your_github_oauth_app_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_app_client_secret
GITHUB_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/auth/github/callback

# OpenAI API Key (required)
OPENAI_API_KEY=your_openai_api_key_here

# GitHub Personal Access Token (optional - for fallback)
GITHUB_TOKEN=your_personal_access_token_here
```

## 3. How It Works

### Public Repositories
- No authentication required
- Works out of the box

### Private Repositories
1. User pastes a private repository URL
2. System detects permission denied error
3. User is prompted to authenticate with GitHub
4. OAuth flow redirects to GitHub for authorization
5. User grants access and is redirected back
6. Access token is stored in session
7. Repository can now be cloned and instrumented

## 4. OAuth Endpoints

- **`/auth/github?repository=owner/repo`** - Initiate OAuth flow
- **`/auth/github/callback`** - Handle OAuth callback
- **`/auth/status`** - Check authentication status
- **`/auth/logout`** - Clear stored tokens

## 5. Security Features

- **CSRF Protection**: State parameter prevents cross-site request forgery
- **Secure Sessions**: Tokens stored with httpOnly cookies
- **Token Validation**: Regular checks ensure tokens are still valid
- **Scoped Access**: Only requests `repo` scope for necessary permissions

## 6. Testing

1. Start the server: `python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
2. Visit: http://127.0.0.1:8000
3. Try a private repository - you'll be prompted to authenticate
4. Complete OAuth flow and repository will be instrumented

## 7. Production Considerations

For production deployment:

1. **Update callback URL** to your production domain
2. **Use HTTPS** for security
3. **Implement proper session storage** (Redis/Database instead of in-memory)
4. **Add token refresh logic** for long-lived sessions
5. **Implement rate limiting** on auth endpoints 