import asyncio
import time
from typing import List, AsyncGenerator, Any

class Ingestor:
    """
    Buffers and batches logs from the Chaos Generator.
    Implements a Tumbling Window: 100 items OR 5 seconds.
    """
    
    BATCH_SIZE_LIMIT = 100
    BATCH_TIME_LIMIT = 5.0

    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False

    async def add_log(self, log: str):
        """
        Push a raw log string into the processing queue.
        """
        await self.queue.put(log)

    async def process_stream(self) -> AsyncGenerator[List[str], None]:
        """
        Consumes the queue and yields batches of logs.
        """
        self.is_running = True
        batch = []
        last_flush_time = time.time()
        
        while self.is_running or not self.queue.empty():
            # Calculate time remaining for the current batch
            time_since_flush = time.time() - last_flush_time
            time_remaining = max(0.0, self.BATCH_TIME_LIMIT - time_since_flush)
            
            try:
                # Wait for next log, but timeout if batch time limit reached
                # If batch is empty, we technically don't need to force flush empty batch,
                # but if we want strict windowing we might. 
                # Specs say: "Collect logs for 5 seconds OR until buffer hits 100 items."
                # Usually implies if we have items, flush after 5s. If empty, maybe wait?
                # Let's wait for data.
                
                if len(batch) > 0:
                    # If we have data, we must respect the timeout
                    log = await asyncio.wait_for(self.queue.get(), timeout=time_remaining)
                else:
                    # If empty, just wait indefinitely (or check is_running)
                    # Use a small timeout to check is_running periodically if needed, 
                    # but pure receive is fine if we push a Sentinel/None to stop.
                    # Since we use is_running flag, we might get stuck in await if no logs come.
                    # Ideally we use a timeout or sentinel.
                    # Let's use a 1s timeout to check is_running
                    log = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                batch.append(log)
                
                # Check size limit
                if len(batch) >= self.BATCH_SIZE_LIMIT:
                    yield batch
                    batch = []
                    last_flush_time = time.time()

            except asyncio.TimeoutError:
                # Timeout reached
                if len(batch) > 0:
                    yield batch
                    batch = []
                    last_flush_time = time.time()
                else:
                    # just a heartbeat check loop if empty
                    # reset timer so we don't loop tight if 100% idle? 
                    # actually if empty we just go back to wait.
                    # but if we timed out on empty batch (1.0s check), update last_flush?
                    # No, strictly speaking the window starts when first item arrives or from last flush?
                    # "Collect logs for 5 seconds".
                    # Let's stick to simple: flush if > 0 and time passed.
                    pass
            except Exception as e:
                print(f"Error in ingestor: {e}")
                # preventing crash
                pass

            # Check time limit explicitly again just in case (e.g. if we didn't timeout but processed fast)
            if len(batch) > 0 and (time.time() - last_flush_time >= self.BATCH_TIME_LIMIT):
                yield batch
                batch = []
                last_flush_time = time.time()
                
            if not self.is_running and self.queue.empty():
                break
                
        # Flush remaining
        if batch:
            yield batch
