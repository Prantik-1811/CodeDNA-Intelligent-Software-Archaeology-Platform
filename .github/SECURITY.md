# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in CodeDNA, please report it to us
privately. Do not open a public GitHub issue for security vulnerabilities.

### How to Report

Email the maintainers at [INSERT_SECURITY_EMAIL] with:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes or mitigations

### What to Expect

- You will receive an acknowledgment within 72 hours
- We will provide a timeline for remediation within 7 days
- You will be kept informed of progress throughout the process
- Credit will be given in release notes if desired

## Security Best Practices for Contributors

- Never commit secrets, API keys, or credentials to the repository
- Use environment variables for configuration
- Review dependencies for known vulnerabilities before adding them
- Follow the principle of least privilege in code changes

## Disclosure Policy

Once a vulnerability is confirmed, we will:
1. Assign a CVE identifier (if applicable)
2. Prepare a fix and test it thoroughly
3. Publish a security advisory on GitHub
4. Release a patched version
5. Notify affected users
