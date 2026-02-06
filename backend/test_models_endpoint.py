"""Test script to verify models endpoint returns full list."""
import asyncio
import httpx
import json

async def test_models_endpoint():
    """Test the models endpoint."""
    base_url = "http://localhost:8000"
    
    print("Testing /api/v1/gateway/models endpoint...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Get all models (no provider filter)
        print("\n1. Fetching ALL models (no provider filter)...")
        try:
            response = await client.get(f"{base_url}/api/v1/gateway/models")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            print(f"   ✓ Got {len(models)} models")
            print(f"   Models: {models[:10]}..." if len(models) > 10 else f"   Models: {models}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Test 2: Get OpenAI models only
        print("\n2. Fetching OpenAI models only...")
        try:
            response = await client.get(f"{base_url}/api/v1/gateway/models?provider=openai")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            print(f"   ✓ Got {len(models)} OpenAI models")
            print(f"   Models: {models[:10]}..." if len(models) > 10 else f"   Models: {models}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Test 3: Get Anthropic models only
        print("\n3. Fetching Anthropic models only...")
        try:
            response = await client.get(f"{base_url}/api/v1/gateway/models?provider=anthropic")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            print(f"   ✓ Got {len(models)} Anthropic models")
            print(f"   Models: {models}")
        except Exception as e:
            print(f"   ✗ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_models_endpoint())
