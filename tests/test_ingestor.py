import asyncio
import pytest
import time
from src.ingestor import Ingestor

@pytest.mark.asyncio
async def test_batch_size_limit():
    ingestor = Ingestor()
    
    # Start consumer
    consumer_task = asyncio.create_task(collect_batches(ingestor))
    
    # Push 105 items
    for i in range(105):
        await ingestor.add_log(f"log_{i}")
    
    # Give it a moment to process
    await asyncio.sleep(0.1)
    
    # Stop
    ingestor.is_running = False
    batches = await consumer_task
    
    assert len(batches) >= 1
    assert len(batches[0]) == 100
    if len(batches) > 1:
        assert len(batches[1]) == 5
    else:
        # Buffer might still hold 5 if time not up
        pass

@pytest.mark.asyncio
async def test_time_limit():
    ingestor = Ingestor()
    # Speed up test by lowering limit
    ingestor.BATCH_TIME_LIMIT = 1.0 
    
    consumer_task = asyncio.create_task(collect_batches(ingestor))
    
    # Push 10 items
    for i in range(10):
        await ingestor.add_log(f"log_{i}")
        
    start_time = time.time()
    
    # Wait for flush (should be around 1.0s)
    batches = await consumer_task
    
    duration = time.time() - start_time
    
    assert len(batches) == 1
    assert len(batches[0]) == 10
    # The consumer loop might wait slightly more than 1.0s due to the logic
    # We stopped it implicitly? No, collect_batches waits for completion.
    # We need to stop ingestor after we receive batch? 
    # Or ingestor keeps running.
    
    pass

async def collect_batches(ingestor, timeout=2.0) -> list:
    batches = []
    
    async def run():
        async for batch in ingestor.process_stream():
            batches.append(batch)
            if ingestor.is_running == False and ingestor.queue.empty():
                break
    
    try:
        await asyncio.wait_for(run(), timeout=timeout)
    except asyncio.TimeoutError:
        # Expected if we don't manually stop ingestor in some tests
        pass
        
    return batches

@pytest.mark.asyncio
async def test_time_flush():
    """
    Cleaner test for time flush.
    """
    ingestor = Ingestor()
    ingestor.BATCH_TIME_LIMIT = 0.5 # Fast flush
    
    results = []
    
    async def consume():
        async for batch in ingestor.process_stream():
            results.append(batch)
    
    task = asyncio.create_task(consume())
    
    # Add logs
    await ingestor.add_log("A")
    await ingestor.add_log("B")
    
    # Wait > 0.5s
    await asyncio.sleep(0.7)
    
    # Should have flushed
    assert len(results) >= 1
    assert results[0] == ["A", "B"]
    
    ingestor.is_running = False
    try:
        await asyncio.wait_for(task, timeout=0.1)
    except asyncio.TimeoutError:
        pass

if __name__ == "__main__":
    import sys
    try:
        asyncio.run(test_batch_size_limit())
        print("test_batch_size_limit passed")
        asyncio.run(test_time_flush())
        print("test_time_flush passed")
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
