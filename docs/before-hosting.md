## Required Before Public Hosting

- [x] `DEBUG=False`
- [ ] Proper `ALLOWED_HOSTS`
- [ ] HTTPS enabled
- [ ] Secure session cookies
- [ ] Secure CSRF cookies
- [ ] HSTS enabled after HTTPS is confirmed
- [ ] Secrets in environment variables only
- [ ] Production database configured
- [ ] Backups configured
- [ ] Cross-user access tests passing
- [ ] Login/recovery rate limits passing
- [ ] Password reset/recovery does not reveal whether email exists
- [ ] OAuth token storage secured before storing real Gmail tokens
- [ ] Gmail OAuth production redirect URI configured
- [ ] Dependency audit run
- [ ] Error monitoring/logging configured
