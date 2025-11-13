# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Currently supported versions:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| develop | :white_check_mark: |

## Reporting a Vulnerability

The DynoAI_3 team takes security bugs seriously. We appreciate your efforts to responsibly disclose your findings.

### How to Report a Security Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them using one of the following methods:

1. **GitHub Security Advisories** (Preferred):
   - Go to https://github.com/rob9206/DynoAI_3/security/advisories/new
   - Click "New draft security advisory"
   - Fill in the details of the vulnerability

2. **Direct Contact**:
   - If you prefer not to use GitHub's security advisory feature, you can contact the maintainers directly
   - Include the word "SECURITY" in the subject line

### What to Include in Your Report

Please include the following information in your report:

- **Description**: A clear description of the vulnerability
- **Impact**: The potential impact of the vulnerability
- **Affected Components**: Which parts of the codebase are affected
- **Steps to Reproduce**: Detailed steps to reproduce the vulnerability
- **Proof of Concept**: If possible, include a proof of concept
- **Suggested Fix**: If you have suggestions for fixing the vulnerability
- **Your Contact Information**: So we can follow up with you

### Example Report

```
Subject: SECURITY - [Brief description of vulnerability]

Description:
A detailed description of the security vulnerability...

Impact:
The vulnerability could allow an attacker to...

Affected Components:
- core/authentication.py
- experiments/protos/data_handler.py

Steps to Reproduce:
1. ...
2. ...
3. ...

Proof of Concept:
[Code or steps demonstrating the vulnerability]

Suggested Fix:
[Your suggestions, if any]
```

## Response Timeline

- **Initial Response**: Within 48 hours of receiving your report
- **Status Update**: Within 7 days with our assessment
- **Fix Timeline**: Depends on severity and complexity
  - Critical: Within 7-14 days
  - High: Within 14-30 days
  - Medium: Within 30-60 days
  - Low: Next regular release cycle

## Disclosure Policy

- Security vulnerabilities will be disclosed publicly after a fix is available
- We will credit reporters in the security advisory (unless they prefer to remain anonymous)
- We aim to coordinate disclosure with the reporter

## Security Best Practices for Contributors

### Code Review

All code changes go through:
1. Automated security scanning (CodeQL)
2. Dependency review
3. Human code review

### Math-Critical Code Security

Code in `core/` and `experiments/protos/` requires special attention:

- **Input Validation**: Always validate inputs to mathematical functions
- **Numerical Stability**: Consider edge cases that could cause numerical instability
- **Boundary Conditions**: Test and handle boundary conditions properly
- **Integer Overflow**: Be aware of potential integer overflow in calculations
- **Division by Zero**: Check for division by zero

### Common Vulnerabilities to Avoid

1. **Code Injection**
   - Never use `eval()` or `exec()` with untrusted input
   - Sanitize all user inputs
   - Use parameterized queries for database operations

2. **Path Traversal**
   - Validate and sanitize file paths
   - Use `os.path.join()` and `os.path.normpath()`
   - Never trust user-supplied paths directly

3. **Dependency Vulnerabilities**
   - Keep dependencies up to date
   - Review dependency security advisories
   - Use `pip-audit` or similar tools

4. **Information Disclosure**
   - Don't log sensitive information
   - Be careful with error messages
   - Don't expose internal paths or system information

5. **Insecure Deserialization**
   - Avoid pickle with untrusted data
   - Use JSON or other safe formats when possible
   - Validate deserialized data

### Secure Coding Checklist

- [ ] Input validation for all external inputs
- [ ] Proper error handling without information leakage
- [ ] No hardcoded secrets or credentials
- [ ] Dependencies are up to date and secure
- [ ] No use of dangerous functions (`eval`, `exec`, `pickle.loads` with untrusted data)
- [ ] File operations use safe path handling
- [ ] Math operations handle edge cases and avoid overflow
- [ ] Sensitive data is not logged

## Security Scanning

Our CI/CD pipeline includes:

- **CodeQL**: Automated code scanning for security vulnerabilities
- **Dependency Review**: Checks for known vulnerabilities in dependencies
- **Python Security**: Bandit and other Python security tools

## Security Updates

Security updates are released as soon as possible after a vulnerability is confirmed and fixed:

1. Fix is developed and tested
2. Security advisory is created
3. Fix is merged and released
4. Advisory is published with credit to reporter
5. Users are notified through GitHub releases and security advisories

## Bug Bounty Program

We currently do not have a bug bounty program, but we deeply appreciate security researchers who report vulnerabilities responsibly.

## Hall of Fame

We recognize security researchers who have helped improve DynoAI_3's security:

<!-- Security researchers who responsibly disclose vulnerabilities will be listed here -->

*No security vulnerabilities have been reported yet.*

## Questions?

If you have questions about this security policy:

- Open a [discussion](https://github.com/rob9206/DynoAI_3/discussions) for general security questions
- Use the private reporting methods above for specific vulnerabilities

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)

---

Thank you for helping keep DynoAI_3 and its users safe! 🔒
