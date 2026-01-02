import asyncio
import json
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import AsyncGenerator, List

@dataclass
class Log:
    timestamp: str
    service: str
    level: str
    message: str

class ChaosGenerator:
    """
    Simulates a stream of logs with variable rates and specific patterns.
    """
    
    SERVICES = [
        "payment-gateway", 
        "order-service", 
        "inventory-db", 
        "auth-service", 
        "frontend-proxy",
        "notification-worker"
    ]
    
    LEVELS = ["INFO", "WARN", "ERROR", "DEBUG"]
    
    def __init__(self):
        self.is_running = False
        self._meltdown_mode = False

    def toggle_meltdown(self, enabled: bool):
        self._meltdown_mode = enabled

    async def generate_log_stream(self) -> AsyncGenerator[str, None]:
        """
        Yields a stream of JSON formatted logs.
        """
        self.is_running = True
        
        while self.is_running:
            # Determine rate based on mode
            if self._meltdown_mode:
                # Spike: 500 logs/sec -> 0.002s delay
                # To reduce overhead, we batch generate or sleep shorter.
                # Sleeping 0.002 is tricky in python, better to burst.
                target_rate = 500
                batch_size = 50 # Emit 50 at a time to keep up
                sleep_time = 0.1 # 50 logs every 0.1s = 500 logs/s (approx)
            else:
                # Normal: 10 logs/sec
                target_rate = 10
                batch_size = 1
                sleep_time = 0.1

            logs = self._create_batch(batch_size)
            
            for log in logs:
                yield json.dumps(asdict(log))
            
            await asyncio.sleep(sleep_time)

    def _create_batch(self, count: int) -> List[Log]:
        logs = []
        for _ in range(count):
            logs.append(self._generate_single_log())
        return logs

    def _generate_single_log(self) -> Log:
        # If in meltdown, high chance of specific errors
        if self._meltdown_mode and random.random() < 0.7:
            # Signature pattern
            service = "inventory-db"
            level = "ERROR"
            message = "Database Connection Refused: Pool exhausted"
        else:
            # Random noise
            service = random.choice(self.SERVICES)
            level = random.choice(self.LEVELS)
            message = self._get_random_message(service, level)

        return Log(
            timestamp=datetime.now(timezone.utc).isoformat(),
            service=service,
            level=level,
            message=message
        )

    def _get_random_message(self, service: str, level: str) -> str:
        messages = [
            f"Processing request for {service}",
            "Cache miss",
            "User authenticated successfully",
            "Health check passed",
            "Latency observed",
            "Retrying connection..."
        ]
        return random.choice(messages)

async def main():
    # Manual verification runner
    generator = ChaosGenerator()
    
    print("Starting generator (Normal mode)...")
    
    # Run normal for 2 seconds
    task = asyncio.create_task(run_generator(generator))
    
    await asyncio.sleep(2)
    
    print("\n!!! TRIGGERING MELTDOWN !!!")
    generator.toggle_meltdown(True)
    
    await asyncio.sleep(2)
    
    print("\nStopping...")
    generator.is_running = False
    await task

async def run_generator(gen: ChaosGenerator):
    count = 0
    start = time.time()
    async for log in gen.generate_log_stream():
        count += 1
        # Print first few to verify format, then just dots to show speed
        if count % 100 == 0:
            print(".", end="", flush=True)
        if count < 5 or (count > 500 and count < 505):
             # print a sample
             pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
