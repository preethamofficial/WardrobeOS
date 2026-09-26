"""Account-level app: user profile (home city), data export, account deletion.

Kept separate from allauth's `account` app namespace so template lookups
(`templates/account/`) and URL names never clash.
"""