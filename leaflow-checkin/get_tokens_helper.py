#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cookie Token Extraction Helper for GitHub Actions

This script extracts individual cookie tokens from a full cookie string
and saves them in the required JSON format for the check-in script.

Usage:
    python get_tokens_helper.py
    
For GitHub Actions: Set LEAFLOW_COOKIES environment variable
For local testing: Use the hardcoded cookie string in this file
"""

import json
import os
from urllib.parse import unquote

def parse_cookie_string(cookie_string):
    """
    Parse a cookie string into a dictionary.
    
    Args:
        cookie_string: Raw cookie string from browser
        
    Returns:
        Dictionary of cookie name-value pairs
    """
    cookies = {}
    
    # Split by semicolon and process each cookie
    for cookie in cookie_string.split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            # Split only on first = to handle values with =
            name, value = cookie.split('=', 1)
            cookies[name.strip()] = value.strip()
    
    return cookies

def create_config_from_cookies(cookies):
    """
    Create the configuration structure from parsed cookies.
    
    Args:
        cookies: Dictionary of cookie name-value pairs
        
    Returns:
        Configuration dictionary
    """
    config = {
        "settings": {
            "log_level": "INFO",
            "retry_delay": 3,
            "timeout": 30,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        },
        "accounts": [
            {
                "token_data": {
                    "cookies": cookies
                }
            }
        ]
    }
    
    return config

def main():
    """
    Main function to extract tokens and create config file.
    """
    
    # For GitHub Actions: Read from environment variable
    cookie_string = os.environ.get('LEAFLOW_COOKIES', '')
    
    # For local testing: Hardcoded cookie string
    # This is the full cookie string from the browser
    if not cookie_string:
        cookie_string = """your_cookie_string_here"""
    
    if not cookie_string:
        print("❌ No cookie string provided!")
        print("For GitHub Actions: Set LEAFLOW_COOKIES environment variable")
        print("For local testing: Add cookie string to this script")
        return False
    
    print("📝 Parsing cookie string...")
    
    # Parse the cookie string
    cookies = parse_cookie_string(cookie_string)
    
    # Display found cookies
    print(f"✅ Found {len(cookies)} cookies:")
    for name in cookies.keys():
        # Show first few chars of value for verification (masked for security)
        value_preview = cookies[name][:20] + "..." if len(cookies[name]) > 20 else cookies[name]
        print(f"  - {name}: {value_preview}")
    
    # Create configuration
    config = create_config_from_cookies(cookies)
    
    # Save to file
    output_file = "config.accounts.json"
    print(f"\n💾 Saving configuration to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Configuration saved successfully!")
    print(f"📄 You can now run: python checkin_token.py")
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
