# Security Policy

## Supported Versions

Only the latest release of the Homematic IP Local (HCU) integration receives security updates and bug fixes.

| Version | Supported          |
| ------- | ------------------ |
| Latest release (`main`) | :white_check_mark: |
| Older releases          | :x:                |

---

## Reporting a Vulnerability

The security of this integration and the devices it controls is taken seriously. If you discover a security vulnerability, please report it responsibly.

### How to Submit a Report

**Please DO NOT report security vulnerabilities via public GitHub issues, discussions, or pull requests.**

Instead, report vulnerabilities privately through GitHub:
1. Navigate to the **[Security tab](https://github.com/Ediminator/homematicip-hcu/security)** of the repository.
2. Under "Security advisories", click **Report a vulnerability**.
3. Fill out the advisory form with detailed steps to reproduce the issue.

### What to Include

To help triage and resolve the issue quickly, please include:
- A clear description of the vulnerability.
- Proof-of-concept steps or code to reproduce the issue.
- The potential impact and attack vector (e.g. local network access vs. authenticated Home Assistant user).
- Any proposed remediation or patches, if available.

### What to Expect

- **Acknowledgment**: Because this project is maintained on a volunteer basis in personal spare time, reports will be reviewed on a best-effort basis.
- **Coordination**: We will coordinate with you to validate the vulnerability and prepare a fix prior to public release.
- **Credit**: You will be credited in the security advisory and release notes (unless you prefer anonymity).

---

## Scope & Out of Scope

### Out of Scope
- Vulnerabilities within the underlying **Homematic IP Home Control Unit (HCU)** firmware or eQ-3 hardware/cloud services. Please report these directly to [eQ-3 AG](https://www.eq-3.de/).
- Vulnerabilities in Home Assistant core itself. Please report these directly to the [Home Assistant Security Team](https://www.home-assistant.io/security/).
- Attacks requiring physical access to the HCU or the Home Assistant host machine.
- Deployments where users have deliberately exposed their HCU or Home Assistant instances to the public internet without proper authentication or encryption.
