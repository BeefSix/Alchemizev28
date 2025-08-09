# test_openai.py
import os
from openai import OpenAI

# Read your .env file
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('OPENAI_API_KEY='):
                api_key = line.split('=', 1)[1].strip()
                print(f"API Key found: {api_key[:10]}...{api_key[-4:]}")
                break
else:
    print("❌ .env file not found")
    exit()

# Test OpenAI connection
try:
    client = OpenAI(api_key=api_key)
    
    # Test 1: List models
    print("\n🔍 Testing API connection...")
    models = client.models.list()
    print("✅ API connection successful")
    
    # Test 2: Simple completion
    print("\n🤖 Testing text generation...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'Hello, this is a test!'"}],
        max_tokens=10
    )
    result = response.choices[0].message.content
    print(f"✅ Text generation works: {result}")
    
    # Test 3: Check credits/usage
    print("\n💳 API key seems to be working correctly!")
    
except Exception as e:
    print(f"❌ OpenAI API Error: {e}")
    
    if "authentication" in str(e).lower():
        print("🔑 Issue: Invalid API key")
    elif "quota" in str(e).lower() or "billing" in str(e).lower():
        print("💰 Issue: No credits/billing issue")
    elif "rate" in str(e).lower():
        print("⏰ Issue: Rate limit")
    else:
        print("❓ Unknown API issue")