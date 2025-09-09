#!/usr/bin/env python3
"""
Test script to verify Telegram bot configuration
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_telegram_connection():
    """Test if Telegram bot is properly configured and working"""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token:
        print("❌ TELEGRAM_TOKEN not found in environment variables")
        return False
    
    if not chat_id:
        print("❌ TELEGRAM_CHAT_ID not found in environment variables")
        return False
    
    print(f"✅ Found token: {token[:10]}...")
    print(f"✅ Found chat ID: {chat_id}")
    
    # Test sending a message
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🤖 Job Finder Bot is working! This is a test message.",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Test message sent successfully!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send test message: {e}")
        return False

if __name__ == "__main__":
    print("Testing Telegram bot configuration...")
    test_telegram_connection()
