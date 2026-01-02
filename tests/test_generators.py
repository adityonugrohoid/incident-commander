import asyncio
import json
import pytest
import time
from src.generators import ChaosGenerator

@pytest.mark.asyncio
async def test_log_structure():
    generator = ChaosGenerator()
    gen = generator.generate_log_stream()
    
    # Get one log
    log_json = await anext(gen)
    log = json.loads(log_json)
    
    assert "timestamp" in log
    assert "service" in log
    assert "level" in log
    assert "message" in log
    
    # Clean up
    generator.is_running = False

@pytest.mark.asyncio
async def test_normal_rate():
    generator = ChaosGenerator()
    # Ensure meltdown is off
    generator.toggle_meltdown(False)
    
    start_time = time.time()
    count = 0
    
    # Consume for 1 second
    async for log in generator.generate_log_stream():
        count += 1
        if time.time() - start_time >= 1.0:
            break
            
    generator.is_running = False
    
    # Should be around 10. Allow wide margin due to sleep precision and test overhead.
    assert 5 <= count <= 20, f"Expected around 10 logs, got {count}"

@pytest.mark.asyncio
async def test_meltdown_rate_and_pattern():
    generator = ChaosGenerator()
    generator.toggle_meltdown(True)
    
    start_time = time.time()
    count = 0
    pattern_found = False
    
    # Consume for 1 second
    async for log in generator.generate_log_stream():
        decoded = json.loads(log)
        if "Database Connection Refused" in decoded["message"]:
            pattern_found = True
            
        count += 1
        if time.time() - start_time >= 1.0:
            break
            
    generator.is_running = False
    
    # Should be much higher than 10. Target is 500.
    # Allow some ramp up/overhead, but should be > 100.
    assert count > 100, f"Expected > 100 logs in meltdown, got {count}"
    assert pattern_found, "Did not find signature pattern in meltdown mode"

if __name__ == "__main__":
    # If run directly without pytest
    import sys
    try:
        asyncio.run(test_log_structure())
        print("test_log_structure passed")
        asyncio.run(test_normal_rate())
        print("test_normal_rate passed")
        asyncio.run(test_meltdown_rate_and_pattern())
        print("test_meltdown_rate_and_pattern passed")
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
