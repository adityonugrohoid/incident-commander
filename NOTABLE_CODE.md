# Notable Code: Incident Commander

This document highlights key code sections that demonstrate the technical strengths and architectural patterns implemented in this event-driven AI system.

## Overview

Incident Commander is an event-driven log analysis system that uses tumbling window batching and async architecture to process high-velocity log streams. The system demonstrates production-focused patterns including non-blocking I/O, structured validation, and efficient batching strategies.

---

## 1. Tumbling Window Batching Implementation

**File:** `src/ingestor.py`  
**Lines:** 24-97

The tumbling window pattern is a core strength of this system, efficiently batching logs based on time (5 seconds) or size (100 items) limits.

```python
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
            if len(batch) > 0:
                # If we have data, we must respect the timeout
                log = await asyncio.wait_for(self.queue.get(), timeout=time_remaining)
            else:
                # If empty, use a small timeout to check is_running periodically
                log = await asyncio.wait_for(self.queue.get(), timeout=1.0)

            batch.append(log)
            
            # Check size limit
            if len(batch) >= self.BATCH_SIZE_LIMIT:
                yield batch
                batch = []
                last_flush_time = time.time()

        except asyncio.TimeoutError:
            # Timeout reached - flush current batch
            if len(batch) > 0:
                yield batch
                batch = []
                last_flush_time = time.time()
        
        # Check time limit explicitly
        if len(batch) > 0 and (time.time() - last_flush_time >= self.BATCH_TIME_LIMIT):
            yield batch
            batch = []
            last_flush_time = time.time()
```

**Why it's notable:**
- Implements proper tumbling window logic with dual triggers (time OR size)
- Uses `asyncio.wait_for` with dynamic timeouts for efficient batching
- Handles edge cases (empty batches, timeouts) gracefully
- Non-blocking queue operations prevent UI freezing

---

## 2. Async Event-Driven Architecture

**File:** `src/app.py`  
**Lines:** 50-129

The main monitoring loop demonstrates clean async architecture with concurrent task management.

```python
async def run_monitoring(status_placeholder, stats_placeholder, log_stream_placeholder, incident_placeholder, meltdown_enabled):
    # Initialize Components
    generator = ChaosGenerator()
    ingestor = Ingestor()
    analyzer = Analyzer()
    
    # State tracking
    total_logs_processed = 0
    raw_logs_buffer = []

    # Start the Generator feeding the Ingestor in background
    async def feed_ingestor():
        async for log in generator.generate_log_stream():
            await ingestor.add_log(log)
    
    feed_task = asyncio.create_task(feed_ingestor())
    
    try:
        # Process Batches
        async for batch in ingestor.process_stream():
            batch_size = len(batch)
            total_logs_processed += batch_size
            
            # Update Stats
            stats_placeholder.metric("Logs Processed", total_logs_processed)
            
            # Analyze Batch
            with st.spinner("Analyzing batch..."):
                report = await analyzer.analyze_batch(batch)
            
            # Render Incident Report
            if report.severity == "Critical":
                container = incident_placeholder.container()
                container.error(f"🚨 **{report.title}**")
                # ... render report details

            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        pass
    finally:
        generator.is_running = False
        ingestor.is_running = False
        feed_task.cancel()
```

**Why it's notable:**
- Clean separation of concerns with dedicated async tasks
- Concurrent log generation and processing using `asyncio.create_task`
- Proper cleanup in finally block with task cancellation
- Non-blocking UI updates while processing batches

---

## 3. Pydantic Schema Enforcement for LLM Outputs

**File:** `src/agent.py`  
**Lines:** 11-96

The system uses Pydantic models to enforce structured outputs from the LLM, preventing hallucination and ensuring type safety.

```python
class IncidentReport(BaseModel):
    title: str
    severity: Literal['Critical', 'Warning', 'Info']
    impacted_services: List[str]
    summary: str
    noise_reduction_ratio: float

class Analyzer:
    async def analyze_batch(self, logs: List[str]) -> IncidentReport:
        """
        Sends logs to LLM and returns specific IncidentReport.
        """
        if not logs:
            return self._create_fallback_report("No logs provided")
        
        prompt = self._create_prompt(logs)
        
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            
            response_text = response.text
            # Clean up markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            data = json.loads(response_text)
            
            # Handle potential list response from LLM
            if isinstance(data, list):
                if data:
                    data = data[0]
                else:
                    return self._create_fallback_report("Empty JSON list returned")
            
            # Pydantic validation ensures schema compliance
            return IncidentReport(**data)

        except Exception as e:
            print(f"Analyzer Error: {e}")
            return self._create_fallback_report(str(e))
```

**Why it's notable:**
- Uses Pydantic `BaseModel` for type-safe, validated outputs
- Enforces JSON response format via `response_mime_type`
- Handles LLM response variations (markdown blocks, lists) gracefully
- Fallback mechanism ensures system never crashes on LLM errors
- Type hints (`-> IncidentReport`) provide compile-time safety

---

## 4. Non-Blocking Queue Operations

**File:** `src/ingestor.py`  
**Lines:** 14-22

The ingestor uses `asyncio.Queue` for thread-safe, non-blocking log buffering.

```python
class Ingestor:
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
```

**Why it's notable:**
- `asyncio.Queue` provides thread-safe, async-compatible queue operations
- `await self.queue.put()` is non-blocking, allowing high-throughput log ingestion
- Simple, clean API for adding logs without blocking the producer
- Enables concurrent log generation and processing

---

## Architecture Highlights

### Event-Driven Design
The system follows a clear event-driven architecture:
1. **Log Generator** → emits logs asynchronously
2. **Ingestor** → buffers logs in tumbling windows
3. **Analyzer** → processes batches with LLM
4. **Dashboard** → displays results in real-time

### Design Patterns Used

1. **Tumbling Window Pattern**: Batches events by time or size
2. **Async Generator Pattern**: Uses `AsyncGenerator` for streaming data
3. **Schema Validation Pattern**: Pydantic enforces structure at boundaries
4. **Fallback Pattern**: Graceful degradation on errors
5. **Task-Based Concurrency**: `asyncio.create_task` for concurrent operations

---

## Technical Strengths Demonstrated

- **Non-blocking I/O**: Full async/await usage prevents UI freezing
- **Type Safety**: Pydantic models ensure validated data structures
- **Error Resilience**: Fallback mechanisms prevent system crashes
- **Efficient Batching**: Tumbling window reduces API calls while maintaining responsiveness
- **Clean Architecture**: Clear separation between ingestion, analysis, and presentation layers
