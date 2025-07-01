# Email Notification System Setup

## Overview
Your RomaLume app now has a comprehensive email notification system that allows you to send targeted emails to users based on their preferences.

## Features
- **User Email Preferences**: Users can choose which types of emails they want to receive
- **Admin Email Interface**: Send emails to specific user segments
- **Beautiful Templates**: Professional HTML email templates with RomaLume branding
- **Email Types**: Feature updates, bug fixes, pricing changes, usage tips

## Setup Required

### 1. SendGrid Account
1. Sign up at [SendGrid.com](https://sendgrid.com) (free tier: 100 emails/day)
2. Get your API key from Settings → API Keys
3. Add to your `.env` file:
   ```
   SENDGRID_API_KEY=your_sendgrid_api_key_here
   ```

### 2. Verify Sender Email
1. In SendGrid dashboard, go to Settings → Sender Authentication
2. Verify your domain or at least one sender email
3. Update the `from_email` in `main.py` line ~40:
   ```python
   from_email = Email("your-verified-email@yourdomain.com")
   ```

### 3. Deploy Backend
The backend will automatically deploy to Render when you push to GitHub.

### 4. Deploy Frontend
```bash
cd frontend
npm run build
firebase deploy
```

## How to Use

### For Users
1. Go to Account page → Email Preferences
2. Choose which types of emails to receive
3. Save preferences

### For Admins
1. Go to Admin page → Send Email to Users
2. Choose email type (feature updates, bug fixes, etc.)
3. Write subject and content (supports HTML)
4. Preview recipients
5. Send email

## Email Types
- **🚀 Feature Updates**: New features and improvements
- **🐛 Bug Fixes**: Bug fixes and technical improvements  
- **💰 Pricing Changes**: Pricing and plan updates
- **💡 Usage Tips**: Tips and best practices
- **📢 All Users**: General announcements

## Example Email Content
```html
<h2>New Mobile Features!</h2>
<p>We're excited to announce new mobile features for RomaLume:</p>
<ul>
    <li>📱 Mobile drawer navigation</li>
    <li>⚡ Auto-scroll chat</li>
    <li>🎨 Improved mobile UI</li>
</ul>
<p>Try these features on your mobile device today!</p>
```

## Troubleshooting
- **Emails not sending**: Check SendGrid API key and sender verification
- **No recipients**: Users may have opted out of that email type
- **Template issues**: Check HTML syntax in email content

## Next Steps
1. Set up SendGrid account and API key
2. Verify your sender email
3. Test with a small email to yourself
4. Start sending update emails to your users! 